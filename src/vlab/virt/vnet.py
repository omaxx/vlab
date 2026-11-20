from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Interface
from typing import Literal, Self
import xml.etree.ElementTree as ET

from .meta import tag


@dataclass
class DHCPRange:
    start: str
    end: str


@dataclass
class DHCPHost:
    """Fixed DHCP lease by MAC; name is also served by the network's DNS (dnsmasq)."""

    mac: str
    ip: str  # address only, no prefix
    name: str | None = None

    def to_xml(self) -> ET.Element:
        attrs = {"mac": self.mac, "ip": self.ip}
        if self.name is not None:
            attrs["name"] = self.name
        return ET.Element("host", attrs)

    @classmethod
    def from_xml(cls, xml: ET.Element) -> Self:
        return cls(mac=xml.get("mac", ""), ip=xml.get("ip", ""), name=xml.get("name"))


@dataclass
class DHCP:
    """DHCP on the network's ip; hosts only (no ranges) = fixed leases only."""

    ranges: list[DHCPRange] = field(default_factory=list)
    hosts: list[DHCPHost] = field(default_factory=list)


@dataclass
class VNet:
    """libvirt network: L2 bridge, optional host IP, DHCP, MTU and forwarding.

    forward: None = isolated; nat/route/open = libvirt creates the bridge;
    bridge = wrap an existing host bridge (bridge required; no ip, dhcp, mtu).
    devices: vlab metadata. None = created outside vlab (no metadata), never started/stopped by vlab.
    A list (may be empty, e.g. shared mgmt network) = managed by vlab; names = devices owning it.
    """

    name: str
    bridge: str | None = None  # default: same as name (except forward=bridge: required)
    ip: str | None = None  # host IP with prefix, e.g. "172.255.1.254/24"
    forward: Literal["nat", "route", "open", "bridge"] | None = None
    devices: list[str] | None = None
    mtu: int | None = None  # None = libvirt default (1500)
    dhcp: DHCP | None = None

    @property
    def managed(self) -> bool:
        return self.devices is not None

    def validate(self) -> None:
        """Raise ValueError for combinations libvirt rejects or that can't work."""
        if self.forward == "bridge":
            if self.bridge is None:
                raise ValueError(f"VNet {self.name}: forward=bridge needs bridge (existing host bridge)")
            if self.ip is not None or self.dhcp is not None or self.mtu is not None:
                raise ValueError(f"VNet {self.name}: forward=bridge allows no ip, dhcp or mtu")
        if self.dhcp is not None:
            if self.ip is None:
                raise ValueError(f"VNet {self.name}: dhcp needs ip")
            net = IPv4Interface(self.ip).network
            addrs = [a for r in self.dhcp.ranges for a in (r.start, r.end)] + [h.ip for h in self.dhcp.hosts]
            for a in addrs:
                if IPv4Address(a) not in net:
                    raise ValueError(f"VNet {self.name}: dhcp address {a} not in {net}")

    def to_xml(self) -> str:
        self.validate()
        net = ET.Element("network")
        ET.SubElement(net, "name").text = self.name
        if self.devices is not None:
            meta = ET.SubElement(ET.SubElement(net, "metadata"), tag("network"))
            devices = ET.SubElement(meta, tag("devices"))
            for n in self.devices:
                ET.SubElement(devices, tag("device")).text = n
        if self.forward:
            ET.SubElement(net, "forward", mode=self.forward)
        if self.forward == "bridge":
            ET.SubElement(net, "bridge", name=self.bridge or "")
        else:
            ET.SubElement(net, "bridge", name=self.bridge or self.name, stp="off", delay="0")
        if self.mtu is not None:
            ET.SubElement(net, "mtu", size=str(self.mtu))
        if self.ip:
            iface = IPv4Interface(self.ip)
            ip = ET.SubElement(net, "ip", address=str(iface.ip), prefix=str(iface.network.prefixlen))
            if self.dhcp is not None:
                dhcp = ET.SubElement(ip, "dhcp")
                for r in self.dhcp.ranges:
                    ET.SubElement(dhcp, "range", start=r.start, end=r.end)
                dhcp.extend(h.to_xml() for h in self.dhcp.hosts)
        ET.indent(net)
        return ET.tostring(net, encoding="unicode")

    @classmethod
    def from_xml(cls, xml: str) -> Self:
        net = ET.fromstring(xml)
        bridge = net.find("bridge")
        forward = net.find("forward")
        mtu = net.find("mtu")
        ip = net.find("ip")
        dhcp = ip.find("dhcp") if ip is not None else None
        meta = net.find(f"metadata/{tag('network')}")
        return cls(
            name=net.findtext("name", ""),
            bridge=bridge.get("name") if bridge is not None else None,
            ip=_ip_from_xml(ip),
            forward=forward.get("mode") if forward is not None else None,  # type: ignore[arg-type]
            devices=[d.text or "" for d in meta.iterfind(f"{tag('devices')}/{tag('device')}")] if meta is not None else None,
            mtu=int(mtu.get("size", "0")) if mtu is not None else None,
            dhcp=DHCP(
                ranges=[DHCPRange(r.get("start", ""), r.get("end", "")) for r in dhcp.iterfind("range")],
                hosts=[DHCPHost.from_xml(h) for h in dhcp.iterfind("host")],
            ) if dhcp is not None else None,
        )


def _ip_from_xml(ip: ET.Element | None) -> str | None:
    """libvirt stores either prefix= or netmask= (e.g. the stock 'default' network)."""
    if ip is None or ip.get("address") is None:
        return None
    mask = ip.get("prefix") or ip.get("netmask")
    return str(IPv4Interface(f"{ip.get('address')}/{mask}")) if mask else None
