import xml.etree.ElementTree as ET
import pytest

from vlab.virt import DHCP, DHCPHost, DHCPRange, VNet


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
    vnet = VNet("r1-int", devices=["r1", "r2"])
    xml = vnet.to_xml()
    assert "<vlab:device>r1</vlab:device>" in xml and "<vlab:device>r2</vlab:device>" in xml
    validate_xml(xml, "network", tmp_path)
    assert vnet.managed
    assert not VNet("mgmt-1").managed


def test_from_xml_roundtrip():
    for vnet in (VNet("p2p-1"), VNet("mgmt-1", bridge="br-m", ip="172.255.1.254/24", forward="nat", devices=["r1"])):
        back = VNet.from_xml(vnet.to_xml())
        assert back == VNet(vnet.name, vnet.bridge or vnet.name, vnet.ip, vnet.forward, vnet.devices)


def test_managed_flag():
    assert VNet("mgmt-1", devices=[]).managed  # vlab network shared by all devices
    assert "metadata" in VNet("mgmt-1", devices=[]).to_xml()
    assert not VNet("mgmt-1").managed
    assert "metadata" not in VNet("mgmt-1").to_xml()
    assert VNet.from_xml(VNet("mgmt-1", devices=[]).to_xml()).devices == []
    assert VNet.from_xml(VNet("mgmt-1").to_xml()).devices is None


LEASE = DHCPHost("c0:ff:ee:01:00:01", "172.255.1.1", "vm-01")


def test_mtu(validate_xml, tmp_path):
    xml = VNet("p2p-1", mtu=9000).to_xml()
    assert ET.fromstring(xml).find("mtu").get("size") == "9000"
    validate_xml(xml, "network", tmp_path)
    assert ET.fromstring(VNet("p2p-1").to_xml()).find("mtu") is None


def test_dhcp(validate_xml, tmp_path):
    vnet = VNet("mgmt-1", ip="172.255.1.254/24", forward="nat",
                dhcp=DHCP([DHCPRange("172.255.1.100", "172.255.1.199")], [LEASE]))
    xml = vnet.to_xml()
    dhcp = ET.fromstring(xml).find("ip/dhcp")
    assert dhcp.find("range").attrib == {"start": "172.255.1.100", "end": "172.255.1.199"}
    assert dhcp.find("host").attrib == {"mac": "c0:ff:ee:01:00:01", "ip": "172.255.1.1", "name": "vm-01"}
    validate_xml(xml, "network", tmp_path)


def test_forward_bridge(validate_xml, tmp_path):
    xml = VNet("lan", bridge="br0", forward="bridge").to_xml()
    net = ET.fromstring(xml)
    assert net.find("forward").get("mode") == "bridge"
    assert net.find("bridge").attrib == {"name": "br0"}  # no stp/delay: host bridge isn't libvirt's
    validate_xml(xml, "network", tmp_path)


@pytest.mark.parametrize(
    "vnet, msg",
    [
        (VNet("lan", forward="bridge"), "needs bridge"),
        (VNet("lan", bridge="br0", forward="bridge", ip="10.0.0.1/24"), "no ip, dhcp or mtu"),
        (VNet("lan", bridge="br0", forward="bridge", mtu=9000), "no ip, dhcp or mtu"),
        (VNet("m", dhcp=DHCP()), "dhcp needs ip"),
        (VNet("m", ip="172.255.1.254/24", dhcp=DHCP([DHCPRange("172.255.2.1", "172.255.2.9")])), "not in 172.255.1.0/24"),
        (VNet("m", ip="172.255.1.254/24", dhcp=DHCP(hosts=[DHCPHost("c0:ff:ee:01:00:01", "10.0.0.1")])), "not in"),
    ],
)
def test_validate(vnet, msg):
    with pytest.raises(ValueError, match=msg):
        vnet.to_xml()


def test_from_xml_full_roundtrip():
    for vnet in (
        VNet("m", "m", "172.255.1.254/24", "nat", devices=[], mtu=9000,
             dhcp=DHCP([DHCPRange("172.255.1.100", "172.255.1.199")], [LEASE, DHCPHost("c0:ff:ee:02:00:01", "172.255.1.2")])),
        VNet("lan", "br0", forward="bridge"),
    ):
        assert VNet.from_xml(vnet.to_xml()) == vnet


def test_from_xml_netmask():
    """libvirt's stock 'default' network uses netmask=, not prefix=."""
    xml = "<network><name>default</name><ip address='192.168.122.1' netmask='255.255.255.0'/></network>"
    assert VNet.from_xml(xml).ip == "192.168.122.1/24"
