from dataclasses import dataclass
from ipaddress import IPv4Interface
from typing import Literal
import xml.etree.ElementTree as ET


@dataclass
class VNet:
    """libvirt network: isolated L2 bridge, optional host IP and forwarding."""

    name: str
    bridge: str | None = None  # default: same as name
    ip: str | None = None  # host IP with prefix, e.g. "172.255.1.254/24"
    forward: Literal["nat", "route", "open"] | None = None  # None = isolated

    def to_xml(self) -> str:
        net = ET.Element("network")
        ET.SubElement(net, "name").text = self.name
        if self.forward:
            ET.SubElement(net, "forward", mode=self.forward)
        ET.SubElement(net, "bridge", name=self.bridge or self.name, stp="off", delay="0")
        if self.ip:
            iface = IPv4Interface(self.ip)
            ET.SubElement(net, "ip", address=str(iface.ip), prefix=str(iface.network.prefixlen))
        ET.indent(net)
        return ET.tostring(net, encoding="unicode")
