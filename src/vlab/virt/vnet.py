from dataclasses import dataclass, field
from ipaddress import IPv4Interface
from typing import Literal, Self
import xml.etree.ElementTree as ET

from .meta import tag


@dataclass
class VNet:
    """libvirt network: isolated L2 bridge, optional host IP and forwarding.

    nodes: vlab nodes using this network (metadata). Empty = created outside vlab, never started/stopped by vlab.
    """

    name: str
    bridge: str | None = None  # default: same as name
    ip: str | None = None  # host IP with prefix, e.g. "172.255.1.254/24"
    forward: Literal["nat", "route", "open"] | None = None  # None = isolated
    nodes: list[str] = field(default_factory=list)

    @property
    def managed(self) -> bool:
        return bool(self.nodes)

    def to_xml(self) -> str:
        net = ET.Element("network")
        ET.SubElement(net, "name").text = self.name
        if self.nodes:
            meta = ET.SubElement(ET.SubElement(net, "metadata"), tag("network"))
            nodes = ET.SubElement(meta, tag("nodes"))
            for n in self.nodes:
                ET.SubElement(nodes, tag("node")).text = n
        if self.forward:
            ET.SubElement(net, "forward", mode=self.forward)
        ET.SubElement(net, "bridge", name=self.bridge or self.name, stp="off", delay="0")
        if self.ip:
            iface = IPv4Interface(self.ip)
            ET.SubElement(net, "ip", address=str(iface.ip), prefix=str(iface.network.prefixlen))
        ET.indent(net)
        return ET.tostring(net, encoding="unicode")

    @classmethod
    def from_xml(cls, xml: str) -> Self:
        net = ET.fromstring(xml)
        bridge = net.find("bridge")
        forward = net.find("forward")
        ip = net.find("ip")
        nodes = net.iterfind(f"metadata/{tag('network')}/{tag('nodes')}/{tag('node')}")
        return cls(
            name=net.findtext("name", ""),
            bridge=bridge.get("name") if bridge is not None else None,
            ip=f"{ip.get('address')}/{ip.get('prefix')}" if ip is not None and ip.get("prefix") else None,
            forward=forward.get("mode") if forward is not None else None,  # type: ignore[arg-type]
            nodes=[n.text or "" for n in nodes],
        )
