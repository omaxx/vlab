from collections.abc import Iterator
from contextlib import contextmanager

import libvirt

from ..host import Host
from .vm import VM
from .vnet import VNet


@contextmanager
def _connect(host: Host) -> Iterator[libvirt.virConnect]:
    conn = libvirt.open(host.libvirt_uri)
    try:
        yield conn
    finally:
        conn.close()


def define_vm(host: Host, vm: VM) -> None:
    """Define (create persistent, not start) VM on host from its XML."""
    with _connect(host) as conn:
        conn.defineXML(vm.to_xml(host))


def define_vnet(host: Host, vnet: VNet) -> None:
    """Define (create persistent, not start, no autostart) network on host from its XML."""
    with _connect(host) as conn:
        conn.networkDefineXML(vnet.to_xml())
