from dataclasses import dataclass, field
import logging
from typing import ClassVar

from ..host import Host
from ..virt import VM, DHCPHost, Disk, Interface, VNet
from .device import Device
from .port import Port

logger = logging.getLogger(__name__)

IFNAME_MAX = 15  # Linux interface/bridge name limit


def _ifname(name: str) -> str | None:
    """Host-side interface name if it fits, else None (libvirt picks vnetN)."""
    return name if len(name) <= IFNAME_MAX else None


@dataclass(kw_only=True)
class VMX(Device):
    """Juniper vMX: RE VM(s) <name>~re<slot> + FPC VM <name>~fpc0, internal VNets <name>~int, <name>~fab.

    Images in <host.images_dir>/junos/vmx/<version>/. Per VM folder vms/<vm>/: qcow2 overlays on the
    base images (never copied), copies of the small writable metadata-usb images.
    MACs (id, slot 2 decimal digits): RE ca:ff:ee:<id>:<10+slot>:00 mgmt, :01 int;
    FPC ca:ff:ee:<id>:<slot>:0a mgmt, :0b int, :0c fab, data port i (0-based = ge-0/0/i) :<i>.
    config: juniper.conf text (or config_file on host) put into the RE metadata image, loaded at first boot.
    """

    type: ClassVar[str] = "jnpr/vmx"
    id: int  # 1-99
    version: str  # image folder, e.g. "24.4R1-S2.9"
    re_image: str  # e.g. "junos-vmx-x86-64-24.4R1-S2.9.qcow2"
    fpc_image: str  # e.g. "vFPC-20241118.img" (raw)
    re_memory: int = 1024  # MiB
    re_vcpus: int = 1
    fpc_memory: int = 2048  # MiB
    fpc_vcpus: int = 3
    double_re: bool = False
    mgmt: Port = field(default_factory=lambda: Port(network="mgmt-1"))
    ports: list[Port] = field(default_factory=list)  # data ports ge-0/0/0...
    config: str | None = None
    config_file: str | None = None  # path on host (~ allowed)

    def images_dir(self, host: Host) -> str:
        return f"{host.images_dir}/junos/vmx/{self.version}"

    @property
    def re_slots(self) -> list[int]:
        return [0, 1] if self.double_re else [0]

    def re_name(self, slot: int) -> str:
        return f"{self.name}~re{slot}"

    @property
    def fpc_name(self) -> str:
        return f"{self.name}~fpc0"

    def mac(self, slot: int, nic: int) -> str:
        return f"ca:ff:ee:{self.id:02d}:{slot:02d}:{nic:02x}"

    def re_metadata(self, slot: int) -> str:
        return f"metadata-usb-re{slot}.img" if self.double_re else "metadata-usb-re.img"

    def vnets(self) -> list[VNet]:
        for net in (f"{self.name}~int", f"{self.name}~fab"):
            if len(net) > IFNAME_MAX:  # bridge named like the network
                raise ValueError(f"{self.name}: device name too long, bridge {net!r} > {IFNAME_MAX} chars")
        return [VNet(f"{self.name}~int", devices=[self.name]), VNet(f"{self.name}~fab", devices=[self.name])]

    def vms(self) -> list[VM]:
        res = [
            VM(
                name=self.re_name(slot),
                device=self.name,
                vcpus=self.re_vcpus,
                memory=self.re_memory,
                uefi=False,
                disks=[
                    Disk("junos.qcow2", "vda"),
                    Disk("vmxhdd.qcow2", "vdb"),
                    Disk(self.re_metadata(slot), "vdc", format="raw"),
                ],
                interfaces=[
                    self.mgmt.interface(self.mac(10 + slot, 0x00), f"{self.re_name(slot)}~mgmt"),
                    Interface("network", f"{self.name}~int", target=_ifname(f"{self.re_name(slot)}~int"),
                              mac=self.mac(10 + slot, 0x01)),
                ],
            )
            for slot in self.re_slots
        ]
        fpc = self.fpc_name
        res.append(
            VM(
                name=fpc,
                device=self.name,
                vcpus=self.fpc_vcpus,
                memory=self.fpc_memory,
                uefi=False,
                machine="pc",
                disks=[
                    Disk("fpc.qcow2", "hda", bus="ide"),
                    Disk("metadata-usb-fpc0.img", "sda", format="raw", bus="usb"),
                ],
                interfaces=[
                    self.mgmt.interface(self.mac(0, 0x0A), f"{fpc}~mgmt"),
                    Interface("network", f"{self.name}~int", target=_ifname(f"{fpc}~int"), mac=self.mac(0, 0x0B)),
                    Interface("network", f"{self.name}~fab", target=_ifname(f"{fpc}~fab"), mac=self.mac(0, 0x0C)),
                ] + [
                    p.interface(f"ca:ff:ee:{self.id:02d}:00:{i:02d}", f"{self.name}-0-{i}")
                    for i, p in enumerate(self.ports)
                ],
            )
        )
        return res

    def dhcp_leases(self) -> list[tuple[str, DHCPHost]]:
        """mgmt dhcp: true -> lease for RE0 fxp0 (mgmt ip, device name)."""
        if not self.mgmt.dhcp:
            return []
        if self.mgmt.network is None or self.mgmt.ip is None:
            raise ValueError(f"{self.name}: mgmt dhcp needs network and ip")
        return [(self.mgmt.network, DHCPHost(self.mac(10, 0x00), self.mgmt.ip.split("/")[0], self.name))]

    def config_text(self, host: Host) -> str | None:
        if self.config is not None and self.config_file is not None:
            raise ValueError(f"{self.name}: give config or config_file, not both")
        return host.read(self.config_file) if self.config_file is not None else self.config

    def prepare(self, host: Host, overwrite: bool) -> None:
        config = self.config_text(host)  # read first: fail before changing anything
        img = self.images_dir(host)
        for slot in self.re_slots:
            d = host.vm_dir(self.re_name(slot))
            if self._fresh_dir(host, d, overwrite):
                host.cow(f"{img}/{self.re_image}", f"{d}/junos.qcow2")
                host.cow(f"{img}/vmxhdd.img", f"{d}/vmxhdd.qcow2")
                host.cp(f"{img}/{self.re_metadata(slot)}", f"{d}/{self.re_metadata(slot)}")
                if config is not None:
                    inject_config(host, f"{d}/{self.re_metadata(slot)}", config)
                logger.info("%s: VM `%s`: files created", host, self.re_name(slot))
        d = host.vm_dir(self.fpc_name)
        if self._fresh_dir(host, d, overwrite):
            host.cow(f"{img}/{self.fpc_image}", f"{d}/fpc.qcow2", backing_format="raw")
            host.cp(f"{img}/metadata-usb-fpc0.img", f"{d}/metadata-usb-fpc0.img")
            logger.info("%s: VM `%s`: files created", host, self.fpc_name)

    @staticmethod
    def _fresh_dir(host: Host, d: str, overwrite: bool) -> bool:
        """True if VM folder must be (re)built: missing, or overwrite (then cleared)."""
        if host.exists(d):
            if not overwrite:
                logger.info("%s: %s: files kept", host, d)
                return False
            host.rm(d)
        host.mkdir(d)
        return True


def inject_config(host: Host, image: str, config: str) -> None:
    """Put config/juniper.conf into vmm-config.tgz of a vMX metadata FAT image (mtools, no mount/root)."""
    stage = host.mktemp_dir()
    try:
        tgz, tree = f"{stage}/vmm-config.tgz", f"{stage}/tree"
        host.run("mcopy", "-i", host.expand(image), "::vmm-config.tgz", tgz)
        host.mkdir(f"{tree}/config")
        host.run("tar", "xzf", tgz, "-C", tree)
        host.write(f"{tree}/config/juniper.conf", config)
        host.run("tar", "czf", tgz, "-C", tree, ".")
        host.run("mcopy", "-o", "-i", host.expand(image), tgz, "::vmm-config.tgz")
    finally:
        host.rm(stage)
