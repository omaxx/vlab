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


def test_nodes_metadata(validate_xml, tmp_path):
    vnet = VNet("r1-int", nodes=["r1", "r2"])
    xml = vnet.to_xml()
    assert "<vlab:node>r1</vlab:node>" in xml and "<vlab:node>r2</vlab:node>" in xml
    validate_xml(xml, "network", tmp_path)
    assert vnet.managed
    assert not VNet("mgmt-1").managed


def test_from_xml_roundtrip():
    for vnet in (VNet("p2p-1"), VNet("mgmt-1", bridge="br-m", ip="172.255.1.254/24", forward="nat", nodes=["r1"])):
        back = VNet.from_xml(vnet.to_xml())
        assert back == VNet(vnet.name, vnet.bridge or vnet.name, vnet.ip, vnet.forward, vnet.nodes)
