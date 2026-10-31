from collections.abc import Iterator
from contextlib import contextmanager

import libvirt

from ..node import Node
from .vm import VM
from .vnet import VNet


@contextmanager
def _connect(node: Node) -> Iterator[libvirt.virConnect]:
    conn = libvirt.open(node.libvirt_uri)
    try:
        yield conn
    finally:
        conn.close()


def define_vm(node: Node, vm: VM) -> None:
    """Define (create persistent, not start) VM on node from its XML."""
    with _connect(node) as conn:
        conn.defineXML(vm.to_xml(node))


def define_vnet(node: Node, vnet: VNet) -> None:
    """Define (create persistent, not start, no autostart) network on node from its XML."""
    with _connect(node) as conn:
        conn.networkDefineXML(vnet.to_xml())
