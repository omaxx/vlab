import xml.etree.ElementTree as ET

from vlab.host import Host
from vlab.virt import VM, Interface


def make_vm(**kw) -> VM:
    return VM(
        "vm-01",
        interfaces=[Interface(network="mgmt-1", mac="c0:ff:ee:01:00:01"), Interface(network="p2p-1", mac="c0:ff:ee:01:00:02")],
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


def test_disk_and_seed_paths_from_host():
    dom = ET.fromstring(make_vm().to_xml(Host(vm_path="/srv/lab")))
    sources = [d.find("source").get("file") for d in dom.iter("disk")]
    assert sources == ["/srv/lab/vms/vm-01/vm-01.qcow2", "/srv/lab/vms/vm-01/seed.iso"]


def test_no_seed():
    dom = ET.fromstring(make_vm(seed=False).to_xml(Host()))
    assert [d.get("device") for d in dom.iter("disk")] == ["disk"]


def test_bios():
    dom = ET.fromstring(make_vm(uefi=False).to_xml(Host()))
    assert dom.find("os").get("firmware") is None


def test_interfaces_in_order():
    dom = ET.fromstring(make_vm().to_xml(Host()))
    ifaces = [(i.find("source").get("network"), i.find("mac").get("address")) for i in dom.iter("interface")]
    assert ifaces == [("mgmt-1", "c0:ff:ee:01:00:01"), ("p2p-1", "c0:ff:ee:01:00:02")]


def test_interface_needs_network_or_bridge():
    import pytest
    with pytest.raises(ValueError):
        Interface()
    with pytest.raises(ValueError):
        Interface(network="a", bridge="b")


def test_bridge_interface(validate_xml, tmp_path):
    xml = VM("vm-01", interfaces=[Interface(bridge="br0")]).to_xml(Host())
    iface = ET.fromstring(xml).find("devices/interface")
    assert iface.get("type") == "bridge"
    assert iface.find("source").attrib == {"bridge": "br0"}
    assert iface.find("mac") is None  # libvirt generates
    validate_xml(xml, "domain", tmp_path)


def test_node_metadata(validate_xml, tmp_path):
    xml = make_vm(node="r1").to_xml(Host())
    ns = "{https://omaxx.net/vlab}"
    assert ET.fromstring(xml).findtext(f"metadata/{ns}domain/{ns}node") == "r1"
    validate_xml(xml, "domain", tmp_path)
    assert "metadata" not in make_vm().to_xml(Host())


def test_from_xml_roundtrip():
    vm = VM(
        "r1", node="r1", vcpus=2, memory=2048,
        interfaces=[Interface(network="mgmt-1", mac="c0:ff:ee:01:00:01"), Interface(bridge="br0", mac="c0:ff:ee:01:00:02")],
    )
    back = VM.from_xml(vm.to_xml(Host()))
    assert back.disks == ["/var/lib/vlab/vms/r1/r1.qcow2", "/var/lib/vlab/vms/r1/seed.iso"]
    back.disks = []
    assert back == vm
    assert back.networks() == ["mgmt-1"]


def test_from_xml_libvirt_running_domain():
    """libvirt XML: memory in KiB, network NICs of running VMs also carry bridge=."""
    xml = """<domain type='kvm'><name>vm-01</name><memory unit='KiB'>4194304</memory><vcpu placement='static'>1</vcpu>
      <os firmware='efi'><type>hvm</type><nvram>/x</nvram></os>
      <devices><interface type='network'><mac address='c0:ff:ee:01:00:01'/>
      <source network='mgmt-1' portid='abc' bridge='mgmt-1'/><model type='virtio'/></interface></devices></domain>"""
    vm = VM.from_xml(xml)
    assert (vm.memory, vm.uefi, vm.seed, vm.node) == (4096, True, False, None)
    assert vm.interfaces == [Interface(network="mgmt-1", mac="c0:ff:ee:01:00:01")]
