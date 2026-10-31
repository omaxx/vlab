"""virt.api against libvirt's in-memory test driver (test:///default): real libvirt, no system changes.

The driver drops its state when the last connection closes, so the fixture keeps one open per test.
"""

import libvirt
import pytest

from vlab.node import Node
from vlab.virt import VM, VNet, Interface, define_vm, define_vnet


@pytest.fixture
def node():
    return Node(libvirt_uri="test:///default")


@pytest.fixture
def conn(node):
    c = libvirt.open(node.libvirt_uri)
    yield c
    c.close()


def test_define_vnet_nat(node, conn):
    define_vnet(node, VNet("mgmt-1", ip="172.255.1.254/24", forward="nat"))
    net = conn.networkLookupByName("mgmt-1")
    assert net.isPersistent()
    assert not net.isActive()
    assert not net.autostart()
    assert net.bridgeName() == "mgmt-1"
    assert "<forward mode='nat'" in net.XMLDesc()
    assert "<ip address='172.255.1.254' prefix='24'" in net.XMLDesc()


def test_define_vnet_isolated(node, conn):
    define_vnet(node, VNet("p2p-1"))
    xml = conn.networkLookupByName("p2p-1").XMLDesc()
    assert "<forward" not in xml
    assert "<ip" not in xml


def test_define_vnet_existing_name_fails(node, conn):
    define_vnet(node, VNet("p2p-1"))
    with pytest.raises(libvirt.libvirtError, match="already exists"):
        define_vnet(node, VNet("p2p-1"))


def test_define_vm(node, conn):
    vm = VM("vm-01", vcpus=2, memory=2048, interfaces=[Interface("mgmt-1", "c0:ff:ee:01:00:01")])
    define_vm(node, vm)
    dom = conn.lookupByName("vm-01")
    assert dom.isPersistent()
    assert not dom.isActive()
    assert dom.maxMemory() == 2048 * 1024  # KiB
    xml = dom.XMLDesc()
    assert "<mac address='c0:ff:ee:01:00:01'/>" in xml
    assert "<source file='/var/lib/vlab/vms/vm-01/vm-01.qcow2'/>" in xml
    assert "<vcpu placement='static'>2</vcpu>" in xml
