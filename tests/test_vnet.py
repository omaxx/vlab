import xml.etree.ElementTree as ET

from vlab.virt import VNet


def test_isolated_no_ip(validate_xml, tmp_path):
    xml = VNet("p2p-1").to_xml()
    net = ET.fromstring(xml)
    assert net.findtext("name") == "p2p-1"
    assert net.find("bridge").get("name") == "p2p-1"
    assert net.find("forward") is None
    assert net.find("ip") is None
    validate_xml(xml, "network", tmp_path)


def test_nat_with_ip(validate_xml, tmp_path):
    xml = VNet("mgmt-1", ip="172.255.1.254/24", forward="nat").to_xml()
    net = ET.fromstring(xml)
    assert net.find("forward").get("mode") == "nat"
    ip = net.find("ip")
    assert (ip.get("address"), ip.get("prefix")) == ("172.255.1.254", "24")
    validate_xml(xml, "network", tmp_path)


def test_custom_bridge():
    net = ET.fromstring(VNet("lab", bridge="br-lab").to_xml())
    assert net.find("bridge").get("name") == "br-lab"
