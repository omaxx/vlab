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
    vlab metadata <vlab:network>:
      managed=False: none (created outside vlab) - never started/stopped/changed by vlab
      managed=True, devices=None: regular network (Network spec)
      devices=[...]: device network (p2p stub, device-internal) - devices using it; undefined when empty
    """

    name: str
    bridge: str | None = None  # default: same as name (except forward=bridge: required)
    ip: str | None = None  # host IP with prefix, e.g. "172.255.1.254/24"
    forward: Literal["nat", "route", "open", "bridge"] | None = None
    devices: list[str] | None = None  # set -> device network (implies managed)
    mtu: int | None = None  # None = libvirt default (1500)
    dhcp: DHCP | None = None
    managed: bool = False

    def __post_init__(self) -> None:
        if self.devices is not None:
            self.managed = True

    def validate(self) -> None:
        """Raise ValueError for combinations libvirt rejects or that can't work."""
        if len(self.bridge or self.name) > 15:  # Linux interface name limit
            raise ValueError(f"VNet {self.name}: bridge name {self.bridge or self.name!r} longer than 15 chars")
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
        if self.managed:
            ET.SubElement(net, "metadata").append(meta_xml(self.devices))
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
        devices = meta.find(tag("devices")) if meta is not None else None
        return cls(
            name=net.findtext("name", ""),
            bridge=bridge.get("name") if bridge is not None else None,
            ip=_ip_from_xml(ip),
            forward=forward.get("mode") if forward is not None else None,  # type: ignore[arg-type]
            devices=[d.text or "" for d in devices.iterfind(tag("device"))] if devices is not None else None,
            mtu=int(mtu.get("size", "0")) if mtu is not None else None,
            dhcp=DHCP(
                ranges=[DHCPRange(r.get("start", ""), r.get("end", "")) for r in dhcp.iterfind("range")],
                hosts=[DHCPHost.from_xml(h) for h in dhcp.iterfind("host")],
            ) if dhcp is not None else None,
            managed=meta is not None,
        )


def meta_xml(devices: list[str] | None) -> ET.Element:
    """<vlab:network> metadata element, with <vlab:devices> only for device networks."""
    meta = ET.Element(tag("network"))
    if devices is not None:
        elem = ET.SubElement(meta, tag("devices"))
        for d in devices:
            ET.SubElement(elem, tag("device")).text = d
    return meta


def _ip_from_xml(ip: ET.Element | None) -> str | None:
    """libvirt stores either prefix= or netmask= (e.g. the stock 'default' network)."""
    if ip is None or ip.get("address") is None:
        return None
    mask = ip.get("prefix") or ip.get("netmask")
    return str(IPv4Interface(f"{ip.get('address')}/{mask}")) if mask else None
