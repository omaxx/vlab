"""virt.api against libvirt's in-memory test driver (test:///default): real libvirt, no system changes.

The driver drops its state when the last connection closes, so the fixture keeps one open per test.
"""

import libvirt
import pytest

from vlab.host import Host
from vlab.virt import (
    VM, VNet, Interface, define_vm, define_vnet, delete_vms, list_vms, list_vnets,
    start_vms, start_vnets, stop_vms, stop_vnets,
)


@pytest.fixture
def host():
    return Host(uri="test:///default")


@pytest.fixture
def conn(host):
    c = libvirt.open(host.libvirt_uri)
    yield c
    c.close()


def test_define_vnet_nat(host, conn):
    define_vnet(host, VNet("mgmt-1", ip="172.255.1.254/24", forward="nat"))
    net = conn.networkLookupByName("mgmt-1")
    assert net.isPersistent()
    assert not net.isActive()
    assert not net.autostart()
    assert net.bridgeName() == "mgmt-1"
    assert "<forward mode='nat'" in net.XMLDesc()
    assert "<ip address='172.255.1.254' prefix='24'" in net.XMLDesc()


def test_define_vnet_isolated(host, conn):
    define_vnet(host, VNet("p2p-1"))
    xml = conn.networkLookupByName("p2p-1").XMLDesc()
    assert "<forward" not in xml
    assert "<ip" not in xml


def test_define_vnet_existing_name_fails(host, conn):
    define_vnet(host, VNet("p2p-1"))
    with pytest.raises(libvirt.libvirtError, match="already exists"):
        define_vnet(host, VNet("p2p-1"))


def test_define_vm(host, conn):
    vm = VM("vm-01", vcpus=2, memory=2048, interfaces=[Interface(network="mgmt-1", mac="c0:ff:ee:01:00:01")])
    define_vm(host, vm)
    dom = conn.lookupByName("vm-01")
    assert dom.isPersistent()
    assert not dom.isActive()
    assert dom.maxMemory() == 2048 * 1024  # KiB
    xml = dom.XMLDesc()
    assert "<mac address='c0:ff:ee:01:00:01'/>" in xml
    assert "<source file='/var/lib/vlab/vms/vm-01/vm-01.qcow2'/>" in xml
    assert "<vcpu placement='static'>2</vcpu>" in xml


@pytest.fixture
def lab(host, conn):
    """r1 on its own managed lab-1, r1+r2 on shared managed link-12, both on unmanaged infra and a bridge."""
    define_vnet(host, VNet("lab-1", nodes=["r1"]))
    define_vnet(host, VNet("link-12", nodes=["r1", "r2"]))
    define_vnet(host, VNet("infra"))
    conn.networkLookupByName("infra").create()
    for name, nets in (("r1", ["lab-1", "link-12", "infra"]), ("r2", ["link-12", "infra"])):
        ifaces = [Interface(network=n) for n in nets] + [Interface(bridge="br0")]
        define_vm(host, VM(name, node=name, interfaces=ifaces))
    return conn


def active_nets(conn) -> set[str]:
    return {n.name() for n in conn.listAllNetworks() if n.isActive()}


def test_list(host, lab):
    vms = {vm.name: (vm.node, active) for vm, active in list_vms(host)}
    assert vms["r1"] == ("r1", False) and vms["r2"] == ("r2", False)
    nets = {vnet.name: (vnet.nodes, active) for vnet, active in list_vnets(host)}
    assert nets["link-12"] == (["r1", "r2"], False)
    assert nets["infra"] == ([], True)


def test_start_vms_starts_managed_vnets(host, lab):
    start_vms(host, "r1")
    assert lab.lookupByName("r1").isActive()
    assert {"lab-1", "link-12", "infra"} <= active_nets(lab)


def test_unmanaged_vnet_never_started(host, lab):
    lab.networkLookupByName("infra").destroy()
    start_vms(host, "r1")  # real libvirt refuses this VM start; the test driver doesn't check networks
    assert "infra" not in active_nets(lab)
    assert "lab-1" in active_nets(lab)


def test_stop_vms_keeps_vnets_in_use(host, lab):
    start_vms(host, "r1", "r2")
    stop_vms(host, "r1")
    assert not lab.lookupByName("r1").isActive()
    nets = active_nets(lab)
    assert "lab-1" not in nets  # only r1 used it
    assert "link-12" in nets  # r2 still running
    assert "infra" in nets  # unmanaged: never stopped
    stop_vms(host, "r2")
    assert "link-12" not in active_nets(lab)
    assert "infra" in active_nets(lab)


def test_stop_vnets_explicit(host, lab):
    start_vms(host, "r1")
    stop_vnets(host, "lab-1", "infra")  # lab-1 in use, infra unmanaged
    assert {"lab-1", "infra"} <= active_nets(lab)
    start_vnets(host, "link-12")
    stop_vms(host, "r1")
    stop_vnets(host, "link-12")
    assert not {"lab-1", "link-12"} & active_nets(lab)


def test_delete_vms(host, lab):
    start_vms(host, "r1")
    delete_vms(host, "r1")
    assert "r1" not in [vm.name for vm, _ in list_vms(host)]
    assert "lab-1" not in active_nets(lab)
    assert "lab-1" in [n.name() for n in lab.listAllNetworks()]  # stopped, still defined


def test_delete_inactive_vm(host, lab):
    delete_vms(host, "r2")
    assert "r2" not in [vm.name for vm, _ in list_vms(host)]
