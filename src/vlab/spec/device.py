from dataclasses import dataclass
import logging

from mashumaro import DataClassDictMixin

from ..host import Host
from ..virt import VM, VNet, define_vm, delete_vms, start_vms, stop_vms
from .network import define_missing_vnets

logger = logging.getLogger(__name__)


@dataclass
class Device(DataClassDictMixin):
    """Lab device: one or more VMs plus internal VNets. Each device type decides how its VMs are named.

    Every VM carries device=name and every internal VNet devices=[name] as libvirt metadata.
    """

    name: str

    def vms(self) -> list[VM]:
        raise NotImplementedError

    def vnets(self) -> list[VNet]:
        """Internal networks of this device."""
        return []

    def prepare(self, host: Host, overwrite: bool) -> None:
        """Create VM files on host; keep existing ones unless overwrite."""

    def deploy(self, host: Host, overwrite: bool = False) -> None:
        """Define missing internal VNets, prepare files, define VMs (not started)."""
        define_missing_vnets(host, self.vnets())
        self.prepare(host, overwrite)
        for vm in self.vms():
            define_vm(host, vm)

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
