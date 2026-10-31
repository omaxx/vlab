from dataclasses import dataclass, field
import xml.etree.ElementTree as ET

from ..host import Host


@dataclass
class Interface:
    network: str
    mac: str
    model: str = "virtio"


@dataclass
class VM:
    """libvirt domain: UEFI q35 VM with qcow2 disk, optional cloud-init seed, serial console.

    Disk and seed live in host.vm_dir(name): <name>.qcow2, seed.iso.
    Controllers, PCI addresses, loader and NVRAM paths are filled in by libvirt on define.
    """

    name: str
    seed: bool = True  # attach cloud-init seed.iso
    vcpus: int = 1
    memory: int = 4096  # MiB
    interfaces: list[Interface] = field(default_factory=list)
    uefi: bool = True  # BIOS boot loops on this host

    def to_xml(self, host: Host) -> str:
        vm_dir = host.vm_dir(self.name)
        dom = ET.Element("domain", type="kvm")
        ET.SubElement(dom, "name").text = self.name
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

        for i in self.interfaces:
            iface = ET.SubElement(devices, "interface", type="network")
            ET.SubElement(iface, "mac", address=i.mac)
            ET.SubElement(iface, "source", network=i.network)
            ET.SubElement(iface, "model", type=i.model)

        serial = ET.SubElement(devices, "serial", type="pty")
        ET.SubElement(serial, "target", port="0")
        console = ET.SubElement(devices, "console", type="pty")
        ET.SubElement(console, "target", type="serial", port="0")
        rng = ET.SubElement(devices, "rng", model="virtio")
        ET.SubElement(rng, "backend", model="random").text = "/dev/urandom"

        ET.indent(dom)
        return ET.tostring(dom, encoding="unicode")
