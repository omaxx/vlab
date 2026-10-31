import libvirt

from ..node import Node
from .vm import VM


def define_vm(node: Node, vm: VM) -> None:
    """Define (create persistent, not start) VM on node from its XML."""
    conn = libvirt.open(node.libvirt_uri)
    try:
        conn.defineXML(vm.to_xml(node))
    finally:
        conn.close()
