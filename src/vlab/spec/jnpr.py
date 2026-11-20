from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, ClassVar

import jinja2

from ..host import Host
from ..utils import load_file
from ..virt import VM, DHCPHost, Disk, Interface, SysInfo, VNet
from .device import DEVICE_VNET_MTU, Device
from .port import Port

logger = logging.getLogger(__name__)

IFNAME_MAX = 15  # Linux interface/bridge name limit


def _ifname(name: str) -> str | None:
    """Host-side interface name if it fits, else None (libvirt picks vnetN)."""
    return name if len(name) <= IFNAME_MAX else None


@dataclass(kw_only=True)
class Junos(Device):
    """Common part of Juniper virtual devices: RE VM(s) <name>~re<slot> + FPC/PFE VM <name>~fpc0,
    internal VNets <name>~<suffix> owned by the device.

    Images in <host.images_dir>/junos/<model>/<version>/; per VM folder vms/<vm>/ with qcow2 overlays.
    Console telnet ports (Device.telnet_port): RE<slot> n=slot, FPC n=5.
    MACs (id, slot 2 decimal digits): RE ca:ff:ee:<id>:<10+slot>:<nic>, FPC ca:ff:ee:<id>:<slot>:<nic>,
    data port i (0-based, Junos port 0/0/i) ca:ff:ee:<id>:00:<i> with host interface <name>-0-<i>.
    """

    model: ClassVar[str]  # image folder under junos/
    internal: ClassVar[tuple[str, ...]]  # internal VNet suffixes
    version: str  # image folder, e.g. "24.4R1-S2.9"
    re_image: str
    fpc_image: str
    re_memory: int = 1024  # MiB
    re_vcpus: int = 1
    fpc_memory: int = 1024  # MiB
    fpc_vcpus: int = 1
    mgmt: Port = field(default_factory=lambda: Port(network="mgmt-1"))
    ports: list[Port] = field(default_factory=list)  # data ports, 0-based

    def images_dir(self, host: Host) -> str:
        return f"{host.images_dir}/junos/{self.model}/{self.version}"

    def all_ports(self) -> list[Port]:
        return [self.mgmt, *self.ports]

    def re_name(self, slot: int) -> str:
        return f"{self.name}~re{slot}"

    @property
    def fpc_name(self) -> str:
        return f"{self.name}~fpc0"

    def mac(self, slot: int, nic: int) -> str:
        return f"ca:ff:ee:{self.id:02d}:{slot:02d}:{nic:02x}"

    def vnets(self) -> list[VNet]:
        names = [f"{self.name}~{s}" for s in self.internal]
        for net in names:
            if len(net) > IFNAME_MAX:  # bridge named like the network
                raise ValueError(f"{self.name}: device name too long, bridge {net!r} > {IFNAME_MAX} chars")
        return [VNet(n, devices=[self.name], mtu=DEVICE_VNET_MTU) for n in names]

    def internal_nic(self, vm: str, suffix: str, mac: str) -> Interface:
        return Interface("network", f"{self.name}~{suffix}", target=_ifname(f"{vm}~{suffix}"), mac=mac)

    def mgmt_nic(self, vm: str, mac: str) -> Interface:
        return self.mgmt.interface(mac, f"{vm}~mgmt")

    def data_nics(self) -> list[Interface]:
        return [p.interface(f"ca:ff:ee:{self.id:02d}:00:{i:02d}", f"{self.name}-0-{i}") for i, p in enumerate(self.ports)]

    def dhcp_leases(self) -> list[tuple[str, DHCPHost]]:
        """mgmt dhcp: true -> lease for RE0 mgmt NIC (mgmt ip, device name)."""
        if not self.mgmt.dhcp:
            return []
        if self.mgmt.network is None or self.mgmt.ip is None:
            raise ValueError(f"{self.name}: mgmt dhcp needs network and ip")
        return [(self.mgmt.network, DHCPHost(self.mac(10, 0x00), self.mgmt.ip.split("/")[0], self.name))]

    @staticmethod
    def fresh_dir(host: Host, d: str, overwrite: bool) -> bool:
        """True if VM folder must be (re)built: missing, or overwrite (then cleared)."""
        if host.exists(d):
            if not overwrite:
                logger.info("%s: %s: files kept", host, d)
                return False
            host.rm(d)
        host.mkdir(d)
        return True


@dataclass(kw_only=True)
class VMX(Junos):
    """Juniper vMX: RE(s) (vda junos, vdb vmxhdd, vdc metadata-usb) + FPC (hda raw vFPC overlay, usb metadata),
    internal VNets ~int, ~fab.

    RE NICs: fxp0 mgmt :00, int :01. FPC NICs: mgmt :0a, int :0b, fab :0c, then ge-0/0/i.
    RE SMBIOS as in Juniper's vRE template (product VM-<name>-161-re-<slot>).
    config: Jinja2 template of juniper.conf (name in <spec dir>/configs/ or absolute path), rendered with
    `vars` (+ `device` = this spec) by resolve(); result put into the RE metadata image, loaded at first boot.
    vars: map, or file (.yaml/.json/.jsonnet, relative to spec dir or absolute) loaded by resolve().
    """

    type: ClassVar[str] = "jnpr/vmx"
    model: ClassVar[str] = "vmx"
    internal: ClassVar[tuple[str, ...]] = ("int", "fab")
    fpc_memory: int = 2048
    fpc_vcpus: int = 3
    double_re: bool = False
    config: str | None = None  # juniper.conf Jinja2 template
    vars: dict[str, Any] | str = field(default_factory=dict)  # template variables, or file with them
    rendered_config: str | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def re_slots(self) -> list[int]:
        return [0, 1] if self.double_re else [0]

    def re_metadata(self, slot: int) -> str:
        return f"metadata-usb-re{slot}.img" if self.double_re else "metadata-usb-re.img"

    def vms(self) -> list[VM]:
        res = [
            VM(
                name=self.re_name(slot),
                device=self.name,
                vcpus=self.re_vcpus,
                memory=self.re_memory,
                uefi=False,
                telnet_port=self.telnet_port(slot),
                sysinfo=SysInfo(
                    bios={"vendor": "Juniper"},
                    system={"manufacturer": "VMX", "product": f"VM-{self.name}-161-re-{slot}", "version": "0.1.0"},
                ),
                disks=[
                    Disk("junos.qcow2", "vda"),
                    Disk("vmxhdd.qcow2", "vdb"),
                    Disk(self.re_metadata(slot), "vdc", format="raw"),
                ],
                interfaces=[
                    self.mgmt_nic(self.re_name(slot), self.mac(10 + slot, 0x00)),
                    self.internal_nic(self.re_name(slot), "int", self.mac(10 + slot, 0x01)),
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
                telnet_port=self.telnet_port(5),
                disks=[
                    Disk("fpc.qcow2", "hda", bus="ide"),
                    Disk("metadata-usb-fpc0.img", "sda", format="raw", bus="usb"),
                ],
                interfaces=[
                    self.mgmt_nic(fpc, self.mac(0, 0x0A)),
                    self.internal_nic(fpc, "int", self.mac(0, 0x0B)),
                    self.internal_nic(fpc, "fab", self.mac(0, 0x0C)),
                    *self.data_nics(),
                ],
            )
        )
        return res

    def resolve(self, spec_dir: str) -> None:
        if isinstance(self.vars, str):
            path = Path(self.vars) if Path(self.vars).is_absolute() else Path(spec_dir) / self.vars
            self.vars = {str(k): v for k, v in load_file(str(path)).items()}
        if self.config is not None:
            self.rendered_config = render_template(self.config, spec_dir, device=self, **self.vars)

    def prepare(self, host: Host, overwrite: bool) -> None:
        if self.config is not None and self.rendered_config is None:
            raise ValueError(f"{self.name}: config template not rendered (load spec with load_device)")
        config = self.rendered_config
        img = self.images_dir(host)
        for slot in self.re_slots:
            d = host.vm_dir(self.re_name(slot))
            if self.fresh_dir(host, d, overwrite):
                host.cow(f"{img}/{self.re_image}", f"{d}/junos.qcow2")
                host.cow(f"{img}/vmxhdd.img", f"{d}/vmxhdd.qcow2")
                host.cp(f"{img}/{self.re_metadata(slot)}", f"{d}/{self.re_metadata(slot)}")
                if config is not None:
                    inject_config(host, f"{d}/{self.re_metadata(slot)}", config)
                logger.info("%s: VM `%s`: files created", host, self.re_name(slot))
        d = host.vm_dir(self.fpc_name)
        if self.fresh_dir(host, d, overwrite):
            host.cow(f"{img}/{self.fpc_image}", f"{d}/fpc.qcow2", backing_format="raw")
            host.cp(f"{img}/metadata-usb-fpc0.img", f"{d}/metadata-usb-fpc0.img")
            logger.info("%s: VM `%s`: files created", host, self.fpc_name)


@dataclass(kw_only=True)
class VQFX(Junos):
    """Juniper vQFX: RE (hda) + PFE (hda), both i440fx/IDE/BIOS, internal VNets ~int, ~res.

    RE NICs: em0 mgmt :00, em1 int :01, em2 res :02, then data ports xe-0/0/i (on the RE).
    PFE NICs: mgmt :0a, int :0b. No config injection (no metadata image): factory login.
    """

    type: ClassVar[str] = "jnpr/vqfx"
    model: ClassVar[str] = "vqfx"
    internal: ClassVar[tuple[str, ...]] = ("int", "res")

    def vms(self) -> list[VM]:
        re0, fpc = self.re_name(0), self.fpc_name
        return [
            VM(
                name=re0,
                device=self.name,
                vcpus=self.re_vcpus,
                memory=self.re_memory,
                uefi=False,
                machine="pc",
                telnet_port=self.telnet_port(0),
                disks=[Disk("junos.qcow2", "hda", bus="ide")],
                interfaces=[
                    self.mgmt_nic(re0, self.mac(10, 0x00)),
                    self.internal_nic(re0, "int", self.mac(10, 0x01)),
                    self.internal_nic(re0, "res", self.mac(10, 0x02)),
                    *self.data_nics(),
                ],
            ),
            VM(
                name=fpc,
                device=self.name,
                vcpus=self.fpc_vcpus,
                memory=self.fpc_memory,
                uefi=False,
                machine="pc",
                telnet_port=self.telnet_port(5),
                disks=[Disk("pfe.qcow2", "hda", bus="ide")],
                interfaces=[
                    self.mgmt_nic(fpc, self.mac(0, 0x0A)),
                    self.internal_nic(fpc, "int", self.mac(0, 0x0B)),
                ],
            ),
        ]

    def prepare(self, host: Host, overwrite: bool) -> None:
        img = self.images_dir(host)
        d = host.vm_dir(self.re_name(0))
        if self.fresh_dir(host, d, overwrite):
            host.cow(f"{img}/{self.re_image}", f"{d}/junos.qcow2")
            logger.info("%s: VM `%s`: files created", host, self.re_name(0))
        d = host.vm_dir(self.fpc_name)
        if self.fresh_dir(host, d, overwrite):
            host.cow(f"{img}/{self.fpc_image}", f"{d}/pfe.qcow2")
            logger.info("%s: VM `%s`: files created", host, self.fpc_name)


def render_template(template: str, spec_dir: str, **context: Any) -> str:
    """Render Jinja2 template (name in <spec_dir>/configs/ or absolute path); undefined variables are errors."""
    path = Path(template) if Path(template).is_absolute() else Path(spec_dir) / "configs" / template
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(path.parent),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    return env.get_template(path.name).render(**context)


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
