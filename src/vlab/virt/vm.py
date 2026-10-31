from dataclasses import dataclass, field
from typing import Self
import xml.etree.ElementTree as ET

from ..host import Host
from .meta import tag

KIB = {"KiB": 1, "MiB": 1024, "GiB": 1024**2}


@dataclass
class Interface:
    """NIC attached to a libvirt network or to a host bridge (exactly one of them)."""

    network: str | None = None
    bridge: str | None = None
    mac: str | None = None  # None = libvirt generates
    model: str = "virtio"

    def __post_init__(self) -> None:
        if (self.network is None) == (self.bridge is None):
            raise ValueError("Interface needs exactly one of network or bridge")

    def to_xml(self) -> ET.Element:
        if self.network is not None:
            iface = ET.Element("interface", type="network")
            source = {"network": self.network}
        else:
            iface = ET.Element("interface", type="bridge")
            source = {"bridge": self.bridge}
        if self.mac:
            ET.SubElement(iface, "mac", address=self.mac)
        ET.SubElement(iface, "source", source)
        ET.SubElement(iface, "model", type=self.model)
        return iface

    @classmethod
    def from_xml(cls, xml: ET.Element) -> Self:
        # running domains show both network= and bridge= on network NICs, so go by interface type
        source = xml.find("source")
        src = source.attrib if source is not None else {}
        mac = xml.find("mac")
        model = xml.find("model")
        is_network = xml.get("type") == "network"
        return cls(
            network=src.get("network") if is_network else None,
            bridge=None if is_network else src.get("bridge"),
            mac=mac.get("address") if mac is not None else None,
            model=model.get("type", "virtio") if model is not None else "virtio",
        )


@dataclass
class VM:
    """libvirt domain: UEFI q35 VM with qcow2 disk, optional cloud-init seed, serial console.

    Disk and seed live in host.vm_dir(name): <name>.qcow2, seed.iso.
    Controllers, PCI addresses, loader and NVRAM paths are filled in by libvirt on define.
    """

    name: str
    node: str | None = None  # vlab node this VM belongs to (metadata); None = not managed by vlab
    seed: bool = True  # attach cloud-init seed.iso
    vcpus: int = 1
    memory: int = 4096  # MiB
    interfaces: list[Interface] = field(default_factory=list)
    uefi: bool = True  # BIOS boot loops on this host
    disks: list[str] = field(default_factory=list)  # read from XML only (from_xml); to_xml derives paths from host

    def networks(self) -> list[str]:
        """libvirt networks this VM is attached to (bridges excluded)."""
        return [i.network for i in self.interfaces if i.network is not None]

    def to_xml(self, host: Host) -> str:
        vm_dir = host.vm_dir(self.name)
        dom = ET.Element("domain", type="kvm")
        ET.SubElement(dom, "name").text = self.name
        if self.node is not None:
            meta = ET.SubElement(ET.SubElement(dom, "metadata"), tag("domain"))
            ET.SubElement(meta, tag("node")).text = self.node
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
        disk = ET.SubElement(devices, "disk", type="file", device="disk")
        ET.SubElement(disk, "driver", name="qemu", type="qcow2")
        ET.SubElement(disk, "source", file=f"{vm_dir}/{self.name}.qcow2")
        ET.SubElement(disk, "target", dev="vda", bus="virtio")

        if self.seed:
            cdrom = ET.SubElement(devices, "disk", type="file", device="cdrom")
            ET.SubElement(cdrom, "driver", name="qemu", type="raw")
            ET.SubElement(cdrom, "source", file=f"{vm_dir}/seed.iso")
            ET.SubElement(cdrom, "target", dev="sda", bus="sata")
            ET.SubElement(cdrom, "readonly")

        devices.extend(i.to_xml() for i in self.interfaces)

        serial = ET.SubElement(devices, "serial", type="pty")
        ET.SubElement(serial, "target", port="0")
        console = ET.SubElement(devices, "console", type="pty")
        ET.SubElement(console, "target", type="serial", port="0")
        rng = ET.SubElement(devices, "rng", model="virtio")
        ET.SubElement(rng, "backend", model="random").text = "/dev/urandom"

        ET.indent(dom)
        return ET.tostring(dom, encoding="unicode")

    @classmethod
    def from_xml(cls, xml: str) -> Self:
        dom = ET.fromstring(xml)
        memory = dom.find("memory")
        node = dom.find(f"metadata/{tag('domain')}/{tag('node')}")
        os = dom.find("os")
        return cls(
            name=dom.findtext("name", ""),
            node=node.text if node is not None else None,
            seed=any(d.get("device") == "cdrom" for d in dom.iterfind("devices/disk")),
            vcpus=int(dom.findtext("vcpu", "1")),
            memory=int(memory.text or 0) * KIB[memory.get("unit", "KiB")] // 1024 if memory is not None else 0,
            interfaces=[Interface.from_xml(e) for e in dom.iterfind("devices/interface")],
            uefi=os is not None and os.get("firmware") == "efi",
            disks=[s.get("file", "") for s in dom.iterfind("devices/disk/source")],
        )
