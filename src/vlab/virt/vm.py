from dataclasses import dataclass, field
from typing import Literal, Self, cast
import xml.etree.ElementTree as ET

from ..host import Host
from .meta import tag

KIB = {"KiB": 1, "MiB": 1024, "GiB": 1024**2}
AGENT_CHANNEL = "org.qemu.guest_agent.0"

NicType = Literal["network", "bridge", "udp"]
NicModel = Literal["virtio", "e1000", "e1000e", "rtl8139"]


@dataclass
class Disk:
    """Disk image file: name inside host.vm_dir(vm) or absolute path (from_xml always gives absolute)."""

    file: str
    target: str  # guest device: vda, sda, hda...
    format: Literal["qcow2", "raw"] = "qcow2"
    bus: Literal["virtio", "scsi", "sata", "ide", "usb"] = "virtio"
    device: Literal["disk", "cdrom"] = "disk"

    def path(self, vm_dir: str) -> str:
        return self.file if self.file.startswith("/") else f"{vm_dir}/{self.file}"

    def to_xml(self, vm_dir: str) -> ET.Element:
        disk = ET.Element("disk", type="file", device=self.device)
        ET.SubElement(disk, "driver", name="qemu", type=self.format)
        ET.SubElement(disk, "source", file=self.path(vm_dir))
        ET.SubElement(disk, "target", dev=self.target, bus=self.bus)
        if self.device == "cdrom":
            ET.SubElement(disk, "readonly")
        return disk

    @classmethod
    def from_xml(cls, xml: ET.Element) -> Self:
        driver = xml.find("driver")
        source = xml.find("source")
        target = xml.find("target")
        return cls(
            file=source.get("file", "") if source is not None else "",
            target=target.get("dev", "") if target is not None else "",
            format=driver.get("type", "raw") if driver is not None else "raw",  # type: ignore[arg-type]
            bus=target.get("bus", "virtio") if target is not None else "virtio",  # type: ignore[arg-type]
            device=xml.get("device", "disk"),  # type: ignore[arg-type]
        )


@dataclass
class Interface:
    """NIC on a libvirt network, a host bridge, or a UDP tunnel to another NIC.

    network/bridge: source = network/bridge name; target = host-side interface name (max 15 chars,
    must not start with vnet/vif/macvtap/macvlan - libvirt reserves those; None = vnetN).
    udp: source = remote "addr:port", local = own "addr:port" (the remote NIC uses the swapped pair).
    """

    type: NicType
    source: str
    target: str | None = None
    local: str | None = None
    mac: str | None = None  # None = libvirt generates
    model: NicModel = "virtio"

    def __post_init__(self) -> None:
        if (self.type == "udp") != (self.local is not None):
            raise ValueError("Interface: local is required for udp and only allowed for udp")
        if self.type == "udp" and self.target is not None:
            raise ValueError("Interface: target is not supported for udp")
        if self.target is not None and len(self.target) > 15:
            raise ValueError(f"Interface: target {self.target!r} longer than 15 chars")

    def to_xml(self) -> ET.Element:
        iface = ET.Element("interface", type=self.type)
        if self.mac:
            ET.SubElement(iface, "mac", address=self.mac)
        if self.type == "udp" and self.local is not None:
            addr, port = self.source.rsplit(":", 1)
            local_addr, local_port = self.local.rsplit(":", 1)
            src = ET.SubElement(iface, "source", address=addr, port=port)
            ET.SubElement(src, "local", address=local_addr, port=local_port)
        else:
            ET.SubElement(iface, "source", {self.type: self.source})
            if self.target is not None:
                ET.SubElement(iface, "target", dev=self.target)
        ET.SubElement(iface, "model", type=self.model)
        return iface

    @classmethod
    def from_xml(cls, xml: ET.Element) -> Self:
        # running domains show both network= and bridge= on network NICs, so go by interface type
        type_ = xml.get("type", "")
        source = xml.find("source")
        src = source.attrib if source is not None else {}
        mac = xml.find("mac")
        model = xml.find("model")
        target = xml.find("target")
        local = source.find("local") if source is not None else None
        mac_ = mac.get("address") if mac is not None else None
        model_ = cast(NicModel, model.get("type", "virtio") if model is not None else "virtio")
        if type_ == "udp":
            return cls(
                "udp",
                f"{src.get('address', '')}:{src.get('port', '')}",
                local=f"{local.get('address', '')}:{local.get('port', '')}" if local is not None else ":",
                mac=mac_,
                model=model_,
            )
        return cls(
            cast(NicType, type_),
            src.get(type_, ""),
            target=target.get("dev") if target is not None else None,
            mac=mac_,
            model=model_,
        )


@dataclass
class VM:
    """libvirt domain: UEFI q35 VM with disks, NICs, serial console and QEMU guest agent channel.

    Relative disk files live in host.vm_dir(name).
    Controllers, PCI addresses, loader and NVRAM paths are filled in by libvirt on define.
    """

    name: str
    device: str | None = None  # vlab device this VM belongs to (metadata); None = not managed by vlab
    vcpus: int = 1
    memory: int = 4096  # MiB
    disks: list[Disk] = field(default_factory=list)
    interfaces: list[Interface] = field(default_factory=list)
    uefi: bool = True  # BIOS boot loops on this host

    def networks(self) -> list[str]:
        """libvirt networks this VM is attached to (bridges and udp excluded)."""
        return [i.source for i in self.interfaces if i.type == "network"]

    def to_xml(self, host: Host) -> str:
        vm_dir = host.vm_dir(self.name)
        dom = ET.Element("domain", type="kvm")
        ET.SubElement(dom, "name").text = self.name
        if self.device is not None:
            meta = ET.SubElement(ET.SubElement(dom, "metadata"), tag("domain"))
            ET.SubElement(meta, tag("device")).text = self.device
        ET.SubElement(dom, "memory", unit="MiB").text = str(self.memory)
        ET.SubElement(dom, "vcpu").text = str(self.vcpus)

        os = ET.SubElement(dom, "os", firmware="efi") if self.uefi else ET.SubElement(dom, "os")
        ET.SubElement(os, "type", arch="x86_64", machine="q35").text = "hvm"
        ET.SubElement(os, "boot", dev="hd")

        features = ET.SubElement(dom, "features")
        ET.SubElement(features, "acpi")
        ET.SubElement(features, "apic")
        ET.SubElement(dom, "cpu", mode="host-passthrough")

        devices = ET.SubElement(dom, "devices")
        devices.extend(d.to_xml(vm_dir) for d in self.disks)
        devices.extend(i.to_xml() for i in self.interfaces)

        serial = ET.SubElement(devices, "serial", type="pty")
        ET.SubElement(serial, "target", port="0")
        console = ET.SubElement(devices, "console", type="pty")
        ET.SubElement(console, "target", type="serial", port="0")
        channel = ET.SubElement(devices, "channel", type="unix")
        ET.SubElement(channel, "target", type="virtio", name=AGENT_CHANNEL)
        rng = ET.SubElement(devices, "rng", model="virtio")
        ET.SubElement(rng, "backend", model="random").text = "/dev/urandom"

        ET.indent(dom)
        return ET.tostring(dom, encoding="unicode")

    @classmethod
    def from_xml(cls, xml: str) -> Self:
        dom = ET.fromstring(xml)
        memory = dom.find("memory")
        device = dom.find(f"metadata/{tag('domain')}/{tag('device')}")
        os = dom.find("os")
        return cls(
            name=dom.findtext("name", ""),
            device=device.text if device is not None else None,
            vcpus=int(dom.findtext("vcpu", "1")),
            memory=int(memory.text or 0) * KIB[memory.get("unit", "KiB")] // 1024 if memory is not None else 0,
            disks=[Disk.from_xml(e) for e in dom.iterfind("devices/disk")],
            interfaces=[Interface.from_xml(e) for e in dom.iterfind("devices/interface")],
            uefi=os is not None and os.get("firmware") == "efi",
        )
