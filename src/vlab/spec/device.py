from dataclasses import dataclass
import logging
from typing import ClassVar

from mashumaro import DataClassDictMixin
from mashumaro.config import BaseConfig
from mashumaro.types import Discriminator

from ..host import Host
from ..virt import VM, DHCPHost, VNet, define_vm, delete_vms, set_dhcp_host, start_vms, stop_vms
from .network import define_missing_vnets

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class Device(DataClassDictMixin):
    """Lab device: one or more VMs plus internal VNets. Each device type decides how its VMs are named.

    Every VM carries device=name and every internal VNet devices=[name] as libvirt metadata.
    Subclasses set `type`; Device.from_dict picks the subclass by the spec's `type:` field (required).
    """

    type: ClassVar[str]
    name: str
    id: int  # 1-99, unique per lab: used for MACs and console ports
    telnet: bool = True  # serial console as telnet on 127.0.0.1:<telnet_port(n)>; False = pty (virsh console)

    class Config(BaseConfig):
        discriminator = Discriminator(field="type", include_subtypes=True)

    def telnet_port(self, n: int) -> int | None:
        """Console port of the device's VM n (0-9): 6000 + id*10 + n, None if telnet is off."""
        return 6000 + self.id * 10 + n if self.telnet else None

    def images_dir(self, host: Host) -> str:
        """Base images of this device type: <host.images_dir>/<type>."""
        return f"{host.images_dir}/{self.type}"

    def vms(self) -> list[VM]:
        raise NotImplementedError

    def vnets(self) -> list[VNet]:
        """Internal networks of this device."""
        return []

    def dhcp_leases(self) -> list[tuple[str, DHCPHost]]:
        """Fixed DHCP leases (network name, lease) registered on deploy; removed by delete_vms via MAC."""
        return []

    def prepare(self, host: Host, overwrite: bool) -> None:
        """Create VM files on host; keep existing ones unless overwrite."""

    def deploy(self, host: Host, overwrite: bool = False) -> None:
        """Define missing internal VNets, prepare files, define VMs (not started), register DHCP leases."""
        define_missing_vnets(host, self.vnets())
        self.prepare(host, overwrite)
        for vm in self.vms():
            define_vm(host, vm)
        for network, lease in self.dhcp_leases():
            set_dhcp_host(host, network, lease)

    def start(self, host: Host) -> None:
        start_vms(host, *self.vm_names())

    def stop(self, host: Host) -> None:
        stop_vms(host, *self.vm_names())

    def delete(self, host: Host, keep_files: bool = False) -> None:
        delete(host, *self.vm_names(), keep_files=keep_files)

    def vm_names(self) -> list[str]:
        return [vm.name for vm in self.vms()]


def delete(host: Host, *vm_names: str, keep_files: bool = False) -> None:
    """Delete VMs from libvirt and, unless keep_files, their folders on host."""
    delete_vms(host, *vm_names)
    if keep_files:
        return
    for name in vm_names:
        d = host.vm_dir(name)
        if host.exists(d):
            host.rm(d)
            logger.info("%s: VM `%s`: files deleted", host, name)
