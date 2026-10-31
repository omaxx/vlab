import xml.etree.ElementTree as ET

from vlab.node import Node
from vlab.virt import VM, Interface


def make_vm(**kw) -> VM:
    return VM(
        "vm-01",
        interfaces=[Interface("mgmt-1", "c0:ff:ee:01:00:01"), Interface("p2p-1", "c0:ff:ee:01:00:02")],
        **kw,
    )


def test_xml(validate_xml, tmp_path):
    xml = make_vm(vcpus=2, memory=2048).to_xml(Node())
    dom = ET.fromstring(xml)
    assert dom.findtext("name") == "vm-01"
    assert dom.findtext("vcpu") == "2"
    assert dom.findtext("memory") == "2048"
    assert dom.find("memory").get("unit") == "MiB"
    assert dom.find("os").get("firmware") == "efi"
    assert dom.find("uuid") is None
    validate_xml(xml, "domain", tmp_path)


def test_disk_and_seed_paths_from_node():
    dom = ET.fromstring(make_vm().to_xml(Node(vm_path="/srv/lab")))
    sources = [d.find("source").get("file") for d in dom.iter("disk")]
    assert sources == ["/srv/lab/vms/vm-01/vm-01.qcow2", "/srv/lab/vms/vm-01/seed.iso"]


def test_no_seed():
    dom = ET.fromstring(make_vm(seed=False).to_xml(Node()))
    assert [d.get("device") for d in dom.iter("disk")] == ["disk"]


def test_bios():
    dom = ET.fromstring(make_vm(uefi=False).to_xml(Node()))
    assert dom.find("os").get("firmware") is None


def test_interfaces_in_order():
    dom = ET.fromstring(make_vm().to_xml(Node()))
    ifaces = [(i.find("source").get("network"), i.find("mac").get("address")) for i in dom.iter("interface")]
    assert ifaces == [("mgmt-1", "c0:ff:ee:01:00:01"), ("p2p-1", "c0:ff:ee:01:00:02")]
