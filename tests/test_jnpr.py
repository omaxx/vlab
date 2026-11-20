import shutil
import subprocess

import pytest

from vlab.host import Host
from vlab.spec import VMX, Device, Port
from vlab.spec.jnpr import inject_config
from vlab.utils import load_file
from vlab.virt import DHCPHost, Disk, Interface, VNet

from conftest import TOPOLOGY, FakeHost

IMG = "/var/lib/vlab/images/junos/vmx/24.4R1-S2.9"


def make(name: str = "vmx-1", **kw) -> VMX:
    return VMX(
        name=name, id=3, version="24.4R1-S2.9",
        re_image="junos-vmx-x86-64-24.4R1-S2.9.qcow2", fpc_image="vFPC-20241118.img",
        ports=[Port("p2p-1"), Port("p2p-2")], **kw,
    )


def test_vms_layout():
    re0, fpc = make().vms()
    assert (re0.name, re0.device, re0.vcpus, re0.memory, re0.uefi, re0.machine) == ("vmx-1~re0", "vmx-1", 1, 1024, False, "q35")
    assert re0.disks == [
        Disk("junos.qcow2", "vda"), Disk("vmxhdd.qcow2", "vdb"), Disk("metadata-usb-re.img", "vdc", format="raw"),
    ]
    assert re0.interfaces == [
        Interface("network", "mgmt-1", target="vmx-1~re0~mgmt", mac="ca:ff:ee:03:10:00"),
        Interface("network", "vmx-1~int", target="vmx-1~re0~int", mac="ca:ff:ee:03:10:01"),
    ]
    assert (fpc.name, fpc.vcpus, fpc.memory, fpc.uefi, fpc.machine) == ("vmx-1~fpc0", 3, 2048, False, "pc")
    assert fpc.disks == [
        Disk("fpc.qcow2", "hda", bus="ide"), Disk("metadata-usb-fpc0.img", "sda", format="raw", bus="usb"),
    ]
    assert [(i.source, i.target, i.mac) for i in fpc.interfaces] == [
        ("mgmt-1", "vmx-1~fpc0~mgmt", "ca:ff:ee:03:00:0a"),  # exactly 15 chars: still fits
        ("vmx-1~int", "vmx-1~fpc0~int", "ca:ff:ee:03:00:0b"),
        ("vmx-1~fab", "vmx-1~fpc0~fab", "ca:ff:ee:03:00:0c"),
        ("p2p-1", "vmx-1-0-0", "ca:ff:ee:03:00:00"),  # ge-0/0/0
        ("p2p-2", "vmx-1-0-1", "ca:ff:ee:03:00:01"),  # ge-0/0/1
    ]
    assert len({i.mac for vm in make().vms() for i in vm.interfaces}) == 7  # all MACs unique


def test_long_name_ifname_fallback():
    re0, fpc = make(name="vmx-12").vms()  # "vmx-12~fpc0~mgmt" = 16 chars
    assert fpc.interfaces[0].target is None  # libvirt picks vnetN
    assert re0.interfaces[0].target == "vmx-12~re0~mgmt"


def test_double_re():
    vms = make(double_re=True).vms()
    assert [vm.name for vm in vms] == ["vmx-1~re0", "vmx-1~re1", "vmx-1~fpc0"]
    assert vms[1].disks[2] == Disk("metadata-usb-re1.img", "vdc", format="raw")
    assert vms[1].interfaces[0].mac == "ca:ff:ee:03:11:00"


def test_vnets():
    assert make().vnets() == [VNet("vmx-1~int", devices=["vmx-1"]), VNet("vmx-1~fab", devices=["vmx-1"])]
    with pytest.raises(ValueError, match="too long"):
        make(name="vmx-very-long").vnets()


def test_mgmt_dhcp_lease():
    d = make(mgmt=Port("mgmt-1", "172.255.1.3/24", dhcp=True))
    assert d.dhcp_leases() == [("mgmt-1", DHCPHost("ca:ff:ee:03:10:00", "172.255.1.3", "vmx-1"))]
    assert make().dhcp_leases() == []


def test_images_dir():
    assert make().images_dir(Host()) == IMG


def files_commands(cfg: bool) -> list[tuple[str, ...]]:
    re0, fpc = "/var/lib/vlab/vms/vmx-1~re0", "/var/lib/vlab/vms/vmx-1~fpc0"
    cmds = [
        ("test", "-e", re0), ("mkdir", "-p", re0),
        ("qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", f"{IMG}/junos-vmx-x86-64-24.4R1-S2.9.qcow2", f"{re0}/junos.qcow2"),
        ("qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", f"{IMG}/vmxhdd.img", f"{re0}/vmxhdd.qcow2"),
        ("cp", f"{IMG}/metadata-usb-re.img", f"{re0}/metadata-usb-re.img"),
    ]
    if cfg:
        cmds.append(("mktemp", "-d"))
    cmds += [
        ("test", "-e", fpc), ("mkdir", "-p", fpc),
        ("qemu-img", "create", "-f", "qcow2", "-F", "raw", "-b", f"{IMG}/vFPC-20241118.img", f"{fpc}/fpc.qcow2"),
        ("cp", f"{IMG}/metadata-usb-fpc0.img", f"{fpc}/metadata-usb-fpc0.img"),
    ]
    return cmds


def test_prepare_no_config():
    host = FakeHost()
    make().prepare(host, overwrite=False)
    assert host.commands() == files_commands(cfg=False)


def test_prepare_with_config_file():
    host = FakeHost(files={"/cfg/vmx.conf": "system { host-name vmx-1; }\n"})
    make(config_file="/cfg/vmx.conf").prepare(host, overwrite=False)
    cmds = [c for c in host.commands() if c[0] not in ("mcopy", "tar", "tee", "rm") and c != ("mkdir", "-p", "/tree/config")]
    assert host.commands()[0] == ("cat", "/cfg/vmx.conf")  # read before any change
    assert [c for c in cmds if c[0] != "cat" and not c[-1].endswith("/tree/config")] == files_commands(cfg=True)
    written = [inp for cmd, inp in host.calls if cmd[0] == "tee"]
    assert written == ["system { host-name vmx-1; }\n"]


def test_prepare_existing_kept():
    host = FakeHost(existing={"/var/lib/vlab/vms/vmx-1~re0", "/var/lib/vlab/vms/vmx-1~fpc0"})
    make().prepare(host, overwrite=False)
    assert host.commands() == [("test", "-e", "/var/lib/vlab/vms/vmx-1~re0"), ("test", "-e", "/var/lib/vlab/vms/vmx-1~fpc0")]


def test_config_and_config_file_exclusive():
    with pytest.raises(ValueError, match="not both"):
        make(config="x", config_file="/y").prepare(FakeHost(), overwrite=False)


@pytest.mark.skipif(not (shutil.which("mformat") and shutil.which("mcopy")), reason="mtools not installed")
def test_inject_config_real_fat_image(tmp_path):
    """FAT16 image like vMX metadata-usb: vmm-config.tgz with boot/loader.conf and empty config/."""
    src = tmp_path / "src"
    (src / "boot").mkdir(parents=True)
    (src / "config").mkdir()
    (src / "boot/loader.conf").write_text("vm_retype=\"RE-VMX\"\n")
    subprocess.run(["tar", "czf", tmp_path / "vmm-config.tgz", "-C", src, "."], check=True)
    img = tmp_path / "metadata.img"
    subprocess.run(["mformat", "-C", "-i", img, "-T", "20480", "::"], check=True, capture_output=True)
    subprocess.run(["mcopy", "-i", img, tmp_path / "vmm-config.tgz", "::vmm-config.tgz"], check=True)

    inject_config(Host(), str(img), "system { host-name vmx-1; }\n")

    out = tmp_path / "out.tgz"
    subprocess.run(["mcopy", "-i", img, "::vmm-config.tgz", out], check=True)
    names = subprocess.run(["tar", "tzf", out], check=True, capture_output=True, text=True).stdout.split()
    assert {"./boot/loader.conf", "./config/juniper.conf"} <= set(names)
    conf = subprocess.run(["tar", "xzOf", out, "./config/juniper.conf"], check=True, capture_output=True, text=True).stdout
    assert conf == "system { host-name vmx-1; }\n"


def test_topology_vmx():
    d = Device.from_dict(load_file(str(TOPOLOGY / "test.yaml/vmx-1.yaml")))
    assert isinstance(d, VMX)
    assert (d.name, d.id, d.mgmt.ip, len(d.ports)) == ("vmx-1", 3, "172.255.1.3/24", 2)
    assert d.config is not None and "host-name vmx-1;" in d.config
