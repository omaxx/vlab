import xml.etree.ElementTree as ET

import pytest

from vlab.host import Host
from vlab.virt import VM, Disk, Interface

DISK = Disk("vm-01.qcow2", "vda")
SEED = Disk("seed.iso", "sda", format="raw", bus="sata", device="cdrom")


def make_vm(**kw) -> VM:
    return VM(
        "vm-01",
        disks=[DISK, SEED],
        interfaces=[
            Interface("network", "mgmt-1", mac="c0:ff:ee:01:00:01"),
            Interface("network", "p2p-1", mac="c0:ff:ee:01:00:02"),
        ],
        **kw,
    )


def test_xml(validate_xml, tmp_path):
    xml = make_vm(vcpus=2, memory=2048).to_xml(Host())
    dom = ET.fromstring(xml)
    assert dom.findtext("name") == "vm-01"
    assert dom.findtext("vcpu") == "2"
    assert dom.findtext("memory") == "2048"
    assert dom.find("memory").get("unit") == "MiB"
    assert dom.find("os").get("firmware") == "efi"
    assert dom.find("uuid") is None
    validate_xml(xml, "domain", tmp_path)


def test_guest_agent_channel():
    channel = ET.fromstring(VM("vm-01").to_xml(Host())).find("devices/channel")
    assert channel.get("type") == "unix"
    assert channel.find("target").attrib == {"type": "virtio", "name": "org.qemu.guest_agent.0"}


def test_disks(validate_xml, tmp_path):
    vm = VM("vm-01", disks=[DISK, SEED, Disk("/srv/img/extra.raw", "hdb", format="raw", bus="ide")])
    xml = vm.to_xml(Host(vm_path="/srv/lab"))
    disks = ET.fromstring(xml).findall("devices/disk")
    got = [
        (d.get("device"), d.find("driver").get("type"), d.find("source").get("file"),
         d.find("target").get("dev"), d.find("target").get("bus"), d.find("readonly") is not None)
        for d in disks
    ]
    assert got == [
        ("disk", "qcow2", "/srv/lab/vms/vm-01/vm-01.qcow2", "vda", "virtio", False),
        ("cdrom", "raw", "/srv/lab/vms/vm-01/seed.iso", "sda", "sata", True),
        ("disk", "raw", "/srv/img/extra.raw", "hdb", "ide", False),  # absolute path kept
    ]
    validate_xml(xml, "domain", tmp_path)


def test_no_disks():
    assert ET.fromstring(VM("vm-01").to_xml(Host())).find("devices/disk") is None


def test_bios():
    dom = ET.fromstring(make_vm(uefi=False).to_xml(Host()))
    assert dom.find("os").get("firmware") is None


def test_interfaces_in_order():
    dom = ET.fromstring(make_vm().to_xml(Host()))
    ifaces = [(i.find("source").get("network"), i.find("mac").get("address")) for i in dom.iter("interface")]
    assert ifaces == [("mgmt-1", "c0:ff:ee:01:00:01"), ("p2p-1", "c0:ff:ee:01:00:02")]


@pytest.mark.parametrize(
    "kw",
    [
        {"type": "udp", "source": "1.1.1.1:1"},  # udp without local
        {"type": "network", "source": "n", "local": "1.1.1.1:1"},  # local only for udp
        {"type": "udp", "source": "1.1.1.1:1", "local": "1.1.1.1:2", "target": "t"},  # no target for udp
        {"type": "bridge", "source": "br0", "target": "x" * 16},  # host ifname max 15 chars
    ],
)
def test_interface_invalid(kw):
    with pytest.raises(ValueError):
        Interface(**kw)


def test_bridge_interface(validate_xml, tmp_path):
    xml = VM("vm-01", interfaces=[Interface("bridge", "br0")]).to_xml(Host())
    iface = ET.fromstring(xml).find("devices/interface")
    assert iface.get("type") == "bridge"
    assert iface.find("source").attrib == {"bridge": "br0"}
    assert iface.find("mac") is None  # libvirt generates
    assert iface.find("target") is None  # libvirt names it vnetN
    validate_xml(xml, "domain", tmp_path)


def test_target_and_model(validate_xml, tmp_path):
    xml = VM("vm-01", interfaces=[Interface("network", "p2p-1", target="vm01-p1", model="e1000")]).to_xml(Host())
    iface = ET.fromstring(xml).find("devices/interface")
    assert iface.find("target").get("dev") == "vm01-p1"
    assert iface.find("model").get("type") == "e1000"
    validate_xml(xml, "domain", tmp_path)


def test_udp_interface(validate_xml, tmp_path):
    xml = VM("vm-01", interfaces=[Interface("udp", "127.0.0.1:10002", local="127.0.0.1:10001")]).to_xml(Host())
    iface = ET.fromstring(xml).find("devices/interface")
    assert iface.get("type") == "udp"
    source = iface.find("source")
    assert source.attrib == {"address": "127.0.0.1", "port": "10002"}
    assert source.find("local").attrib == {"address": "127.0.0.1", "port": "10001"}
    validate_xml(xml, "domain", tmp_path)
    assert VM("vm-01", interfaces=[Interface("udp", "a:1", local="a:2")]).networks() == []


def test_device_metadata(validate_xml, tmp_path):
    xml = make_vm(device="r1").to_xml(Host())
    ns = "{https://omaxx.net/vlab}"
    assert ET.fromstring(xml).findtext(f"metadata/{ns}domain/{ns}device") == "r1"
    validate_xml(xml, "domain", tmp_path)
    assert "metadata" not in make_vm().to_xml(Host())


def test_from_xml_roundtrip():
    vm = VM(
        "r1", device="r1", vcpus=2, memory=2048,
        disks=[Disk("/abs/r1.qcow2", "vda"), Disk("/abs/seed.iso", "sda", format="raw", bus="sata", device="cdrom")],
        interfaces=[
            Interface("network", "mgmt-1", target="r1-p1", mac="c0:ff:ee:01:00:01"),
            Interface("bridge", "br0", mac="c0:ff:ee:01:00:02", model="e1000"),
            Interface("udp", "10.0.0.2:10002", local="10.0.0.1:10001", mac="c0:ff:ee:01:00:03"),
        ],
    )
    back = VM.from_xml(vm.to_xml(Host()))
    assert back == vm
    assert back.networks() == ["mgmt-1"]


def test_from_xml_relative_disks_become_absolute():
    back = VM.from_xml(make_vm().to_xml(Host()))
    assert [d.file for d in back.disks] == ["/var/lib/vlab/vms/vm-01/vm-01.qcow2", "/var/lib/vlab/vms/vm-01/seed.iso"]


def test_from_xml_libvirt_running_domain():
    """libvirt XML: memory in KiB, network NICs of running VMs also carry bridge= and an auto vnetN target."""
    xml = """<domain type='kvm'><name>vm-01</name><memory unit='KiB'>4194304</memory><vcpu placement='static'>1</vcpu>
      <os firmware='efi'><type>hvm</type><nvram>/x</nvram></os>
      <devices><interface type='network'><mac address='c0:ff:ee:01:00:01'/>
      <source network='mgmt-1' portid='abc' bridge='mgmt-1'/><target dev='vnet3'/><model type='virtio'/></interface></devices></domain>"""
    vm = VM.from_xml(xml)
    assert (vm.memory, vm.uefi, vm.disks, vm.device) == (4096, True, [], None)
    assert vm.interfaces == [Interface("network", "mgmt-1", target="vnet3", mac="c0:ff:ee:01:00:01")]


def test_sysinfo(validate_xml, tmp_path):
    from vlab.virt import SysInfo
    info = SysInfo({"vendor": "Juniper"}, {"manufacturer": "VMX", "product": "VM-vmx-1-161-re-0", "version": "0.1.0"})
    xml = VM("vm-01", uefi=False, sysinfo=info).to_xml(Host())
    dom = ET.fromstring(xml)
    assert dom.find("os/smbios").get("mode") == "sysinfo"
    assert {e.get("name"): e.text for e in dom.iterfind("sysinfo/system/entry")}["product"] == "VM-vmx-1-161-re-0"
    validate_xml(xml, "domain", tmp_path)
    assert VM.from_xml(xml).sysinfo == info
    assert ET.fromstring(VM("vm-01").to_xml(Host())).find("sysinfo") is None


def test_on_crash():
    assert ET.fromstring(VM("vm-01").to_xml(Host())).findtext("on_crash") == "restart"
    assert VM.from_xml(VM("vm-01", on_crash="destroy").to_xml(Host())).on_crash == "destroy"


def test_telnet_console(validate_xml, tmp_path):
    xml = VM("vm-01", telnet_port=6011).to_xml(Host())
    dom = ET.fromstring(xml)
    for kind in ("serial", "console"):
        el = dom.find(f"devices/{kind}")
        assert el.get("type") == "tcp"
        assert el.find("source").attrib == {"mode": "bind", "host": "127.0.0.1", "service": "6011"}  # localhost only
        assert el.find("protocol").get("type") == "telnet"
    validate_xml(xml, "domain", tmp_path)
    assert VM.from_xml(xml).telnet_port == 6011
    pty = ET.fromstring(VM("vm-01").to_xml(Host())).find("devices/serial")
    assert pty.get("type") == "pty" and pty.find("source") is None
