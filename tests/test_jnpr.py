import shutil
import subprocess

import pytest

from vlab.host import Host
from vlab.spec import VMX, VQFX, Device, Port, load_device
from vlab.spec.jnpr import inject_config
from vlab.utils import load_file
from vlab.virt import DHCPHost, Disk, Interface, VNet

from conftest import TOPOLOGY, FakeHost, yaml_spec

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
    assert make().vnets() == [VNet("vmx-1~int", devices=["vmx-1"], mtu=9100), VNet("vmx-1~fab", devices=["vmx-1"], mtu=9100)]
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


def test_prepare_with_rendered_config():
    host = FakeHost()
    d = make(config="vmx.conf.j2")
    d.rendered_config = "system { host-name vmx-1; }\n"
    d.prepare(host, overwrite=False)
    cmds = [c for c in host.commands() if c[0] not in ("mcopy", "tar", "tee", "rm") and not c[-1].endswith("/tree/config")]
    assert cmds == files_commands(cfg=True)
    assert [inp for cmd, inp in host.calls if cmd[0] == "tee"] == ["system { host-name vmx-1; }\n"]


def test_prepare_requires_rendered_config():
    with pytest.raises(ValueError, match="not rendered"):
        make(config="vmx.conf.j2").prepare(FakeHost(), overwrite=False)


def test_render_template(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/t.j2").write_text("host-name {{ device.name }};\n{% for i in ifs %}{{ i }};\n{% endfor %}")
    d = make(config="t.j2", vars={"ifs": ["ge-0/0/0", "ge-0/0/1"]})
    d.resolve(str(tmp_path))
    assert d.rendered_config == "host-name vmx-1;\nge-0/0/0;\nge-0/0/1;\n"
    abs_tpl = tmp_path / "abs.j2"
    abs_tpl.write_text("{{ x }}")
    d = make(config=str(abs_tpl), vars={"x": "abs"})
    d.resolve("/nonexistent")  # absolute path: spec dir not used
    assert d.rendered_config == "abs"


def test_vars_from_file(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/t.j2").write_text("{{ user }} {{ ip }}")
    (tmp_path / "vars").mkdir()
    (tmp_path / "vars/common.libsonnet").write_text("{ user: 'maxim' }")
    (tmp_path / "vars/vmx-1.jsonnet").write_text("(import 'common.libsonnet') + { ip: '10.0.0.1/32' }")
    d = make(config="t.j2", vars="vars/vmx-1.jsonnet")  # relative to spec dir, imports relative to the vars file
    d.resolve(str(tmp_path))
    assert d.vars == {"user": "maxim", "ip": "10.0.0.1/32"}
    assert d.rendered_config == "maxim 10.0.0.1/32"
    (tmp_path / "abs.yaml").write_text("user: root\nip: 10.0.0.2/32\n")
    d = make(config="t.j2", vars=str(tmp_path / "abs.yaml"))  # absolute path, any spec format
    d.resolve(str(tmp_path))
    assert d.rendered_config == "root 10.0.0.2/32"


def test_vars_file_from_dict_spec(tmp_path):
    (tmp_path / "v.json").write_text('{"x": 1}')
    d = Device.from_dict({"type": "jnpr/vmx", "name": "vmx-1", "id": 1, "version": "v", "re_image": "re.qcow2",
                          "fpc_image": "fpc.img", "vars": "v.json"})
    assert d.vars == "v.json"  # spec keeps the path until resolve()
    d.resolve(str(tmp_path))
    assert d.vars == {"x": 1}


def test_render_undefined_var_fails(tmp_path):
    import jinja2
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/t.j2").write_text("{{ missing }}")
    with pytest.raises(jinja2.UndefinedError, match="missing"):
        make(config="t.j2").resolve(str(tmp_path))


def test_no_config_no_render(tmp_path):
    d = make()
    d.resolve(str(tmp_path))
    assert d.rendered_config is None


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


@pytest.mark.parametrize("ext", ["yaml", "jsonnet"])
def test_topology_vmx(ext):
    d = yaml_spec("vmx-1") if ext == "yaml" else load_device(str(TOPOLOGY / "jsonnet/vmx-1.jsonnet"))
    assert isinstance(d, VMX)
    assert (d.name, d.id, d.mgmt.ip, len(d.ports), d.config) == ("vmx-1", 3, "172.255.1.3/24", 3, "vmx.conf.j2")
    cfg = d.rendered_config
    assert cfg is not None
    for line in ("host-name vmx-1;", "address 172.255.1.3/24;", "ge-0/0/1 {", "address 192.168.2.3/24;",
                 "ge-0/0/2 {", "address 10.1.0.1/24;", "route 10.2.0.0/24 next-hop 192.168.1.5;", "lite-mode;"):
        assert line in cfg


def test_topology_vmx_yaml_equals_jsonnet():
    y = yaml_spec("vmx-1")
    j = load_device(str(TOPOLOGY / "jsonnet/vmx-1.jsonnet"))
    assert y == j and y.rendered_config == j.rendered_config


def make_vqfx(name: str = "vqfx-1", **kw) -> VQFX:
    return VQFX(
        name=name, id=4, version="20.2",
        re_image="vqfx-20.2R1.10-re-qemu.qcow2", fpc_image="vqfx-20.2R1-2019010209-pfe-qemu.qcow",
        ports=[Port("p2p-1"), Port("p2p-2")], **kw,
    )


def test_vqfx_layout():
    re0, pfe = make_vqfx().vms()
    assert (re0.name, re0.machine, re0.uefi, re0.memory, re0.vcpus) == ("vqfx-1~re0", "pc", False, 1024, 1)
    assert re0.disks == [Disk("junos.qcow2", "hda", bus="ide")]
    assert [(i.source, i.target, i.mac) for i in re0.interfaces] == [
        ("mgmt-1", "vqfx-1~re0~mgmt", "ca:ff:ee:04:10:00"),  # em0
        ("vqfx-1~int", "vqfx-1~re0~int", "ca:ff:ee:04:10:01"),  # em1
        ("vqfx-1~res", "vqfx-1~re0~res", "ca:ff:ee:04:10:02"),  # em2 (old code reused :01)
        ("p2p-1", "vqfx-1-0-0", "ca:ff:ee:04:00:00"),  # xe-0/0/0 (old code collided with em0/em1)
        ("p2p-2", "vqfx-1-0-1", "ca:ff:ee:04:00:01"),
    ]
    assert (pfe.name, pfe.machine, pfe.uefi, pfe.memory, pfe.vcpus) == ("vqfx-1~fpc0", "pc", False, 1024, 1)
    assert pfe.disks == [Disk("pfe.qcow2", "hda", bus="ide")]
    assert [(i.source, i.mac) for i in pfe.interfaces] == [("mgmt-1", "ca:ff:ee:04:00:0a"), ("vqfx-1~int", "ca:ff:ee:04:00:0b")]
    assert len({i.mac for vm in make_vqfx().vms() for i in vm.interfaces}) == 7


def test_vqfx_vnets_and_images():
    assert make_vqfx().vnets() == [VNet("vqfx-1~int", devices=["vqfx-1"], mtu=9100), VNet("vqfx-1~res", devices=["vqfx-1"], mtu=9100)]
    assert make_vqfx().images_dir(Host()) == "/var/lib/vlab/images/junos/vqfx/20.2"


def test_vqfx_prepare():
    host = FakeHost()
    make_vqfx().prepare(host, overwrite=False)
    img, re0, pfe = "/var/lib/vlab/images/junos/vqfx/20.2", "/var/lib/vlab/vms/vqfx-1~re0", "/var/lib/vlab/vms/vqfx-1~fpc0"
    assert host.commands() == [
        ("test", "-e", re0), ("mkdir", "-p", re0),
        ("qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", f"{img}/vqfx-20.2R1.10-re-qemu.qcow2", f"{re0}/junos.qcow2"),
        ("test", "-e", pfe), ("mkdir", "-p", pfe),
        ("qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", f"{img}/vqfx-20.2R1-2019010209-pfe-qemu.qcow", f"{pfe}/pfe.qcow2"),
    ]


def test_topology_vqfx():
    d = load_device(str(TOPOLOGY / "yaml/devices/vqfx-1.yaml"))
    assert isinstance(d, VQFX)
    assert (d.name, d.version, d.dhcp_leases()) == (
        "vqfx-1", "20.2", [("mgmt-1", DHCPHost("ca:ff:ee:04:10:00", "172.255.1.4", "vqfx-1"))]
    )


def test_vmx_sysinfo_and_consoles():
    re0, re1, fpc = make(double_re=True).vms()
    assert re0.sysinfo is not None and re0.sysinfo.bios == {"vendor": "Juniper"}
    assert re0.sysinfo.system == {"manufacturer": "VMX", "product": "VM-vmx-1-161-re-0", "version": "0.1.0"}
    assert re1.sysinfo is not None and re1.sysinfo.system["product"] == "VM-vmx-1-161-re-1"
    assert fpc.sysinfo is None
    assert [vm.telnet_port for vm in (re0, re1, fpc)] == [6030, 6031, 6035]  # 6000 + id*10 + n
    assert [vm.telnet_port for vm in make(telnet=False).vms()] == [None, None]


def test_vqfx_consoles():
    assert [vm.telnet_port for vm in make_vqfx().vms()] == [6040, 6045]
