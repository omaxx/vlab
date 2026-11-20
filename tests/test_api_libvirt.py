"""virt.api against libvirt's in-memory test driver (test:///default): real libvirt, no system changes.

The driver drops its state when the last connection closes, so the fixture keeps one open per test.
"""

import libvirt
import pytest

from vlab.host import Host
from vlab.virt import (
    VM, VNet, Disk, Interface, define_vm, define_vnet, delete_vms, list_vms, list_vnets,
    start_vms, start_vnets, stop_vms, stop_vnets, DHCP, DHCPHost, remove_dhcp_host, set_dhcp_host,
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
    vm = VM(
        "vm-01", vcpus=2, memory=2048, disks=[Disk("vm-01.qcow2", "vda")],
        interfaces=[Interface("network", "mgmt-1", mac="c0:ff:ee:01:00:01")],
    )
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
    define_vnet(host, VNet("lab-1", devices=["r1"]))
    define_vnet(host, VNet("link-12", devices=["r1", "r2"]))
    define_vnet(host, VNet("infra"))  # created outside vlab
    conn.networkLookupByName("infra").create()
    for name, nets in (("r1", ["lab-1", "link-12", "infra"]), ("r2", ["link-12", "infra"])):
        ifaces = [Interface("network", n) for n in nets] + [Interface("bridge", "br0")]
        define_vm(host, VM(name, device=name, interfaces=ifaces))
    return conn


def active_nets(conn) -> set[str]:
    return {n.name() for n in conn.listAllNetworks() if n.isActive()}


def test_list(host, lab):
    vms = {vm.name: (vm.device, active) for vm, active in list_vms(host)}
    assert vms["r1"] == ("r1", False) and vms["r2"] == ("r2", False)
    nets = {vnet.name: (vnet.devices, active) for vnet, active in list_vnets(host)}
    assert nets["link-12"] == (["r1", "r2"], False)
    assert nets["infra"] == (None, True)


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


def defined_nets(conn) -> dict[str, list[str] | None]:
    return {n.name(): VNet.from_xml(n.XMLDesc()).devices for n in conn.listAllNetworks()}


def test_delete_vms(host, lab):
    start_vms(host, "r1")
    delete_vms(host, "r1")
    assert "r1" not in [vm.name for vm, _ in list_vms(host)]
    nets = defined_nets(lab)
    assert "lab-1" not in nets  # r1 was its only device: undefined
    assert nets["link-12"] == ["r2"]  # shared: r1 removed from devices, network kept
    assert "infra" in nets  # unmanaged: untouched
    delete_vms(host, "r2")
    assert "link-12" not in defined_nets(lab)


def test_delete_keeps_network_while_device_has_vms_on_it(host, conn):
    define_vnet(host, VNet("d-int", devices=["d"]))
    for name in ("d-a", "d-b"):
        define_vm(host, VM(name, device="d", interfaces=[Interface("network", "d-int")]))
    delete_vms(host, "d-a")
    assert defined_nets(conn)["d-int"] == ["d"]  # d-b still on it
    delete_vms(host, "d-b")
    assert "d-int" not in defined_nets(conn)


def test_attach_vnet(host, conn):
    from vlab.virt import attach_vnet
    attach_vnet(host, VNet("p2p-x", devices=["a"]), "a")
    assert defined_nets(conn)["p2p-x"] == ["a"]  # created from template
    attach_vnet(host, VNet("p2p-x", devices=["b"]), "b")
    attach_vnet(host, VNet("p2p-x", devices=["b"]), "b")  # idempotent
    conn.networkLookupByName("p2p-x").create()
    attach_vnet(host, VNet("p2p-x", devices=["c"]), "c")  # live update on running network
    assert defined_nets(conn)["p2p-x"] == ["a", "b", "c"]
    define_vnet(host, VNet("mgmt", ip="10.5.0.254/24", managed=True))
    attach_vnet(host, VNet("mgmt", devices=["a"]), "a")  # regular network: used as is
    define_vnet(host, VNet("outside"))
    attach_vnet(host, VNet("outside", devices=["a"]), "a")  # unmanaged: untouched
    nets = defined_nets(conn)
    assert nets["mgmt"] is None and nets["outside"] is None
    assert VNet.from_xml(conn.networkLookupByName("mgmt").XMLDesc()).managed


def test_delete_inactive_vm(host, lab):
    delete_vms(host, "r2")
    assert "r2" not in [vm.name for vm, _ in list_vms(host)]


def test_stop_clean_shutdown(host, lab, caplog):
    start_vms(host, "r1")
    with caplog.at_level("INFO"):
        stop_vms(host, "r1", timeout=5)
    assert not lab.lookupByName("r1").isActive()
    assert "STOPPED (forced" not in caplog.text


def test_stop_forced_after_timeout(host, lab, caplog, monkeypatch):
    from vlab.virt import api
    monkeypatch.setattr(api, "_shutdown", lambda host, dom: None)  # guest ignores shutdown request
    monkeypatch.setattr(api, "POLL", 0.01)
    start_vms(host, "r1")
    with caplog.at_level("INFO"):
        stop_vms(host, "r1", timeout=0.05)
    assert not lab.lookupByName("r1").isActive()
    assert "STOPPED (forced after timeout)" in caplog.text


def test_stop_force(host, lab, monkeypatch):
    from vlab.virt import api
    monkeypatch.setattr(api, "_shutdown", lambda host, dom: pytest.fail("no clean shutdown with force"))
    start_vms(host, "r1", "r2")
    stop_vms(host, "r1", "r2", force=True)
    assert not lab.lookupByName("r1").isActive() and not lab.lookupByName("r2").isActive()


def test_define_vm_udp_and_target(host, conn):
    vm = VM("u1", interfaces=[
        Interface("udp", "127.0.0.1:10002", local="127.0.0.1:10001", mac="c0:ff:ee:09:00:01"),
        Interface("bridge", "br0", target="u1-p2", model="e1000"),
    ])
    define_vm(host, vm)
    back = VM.from_xml(conn.lookupByName("u1").XMLDesc())
    assert back.interfaces[0] == vm.interfaces[0]
    assert (back.interfaces[1].target, back.interfaces[1].model) == ("u1-p2", "e1000")



def leases(conn, network):
    vnet = VNet.from_xml(conn.networkLookupByName(network).XMLDesc())
    return vnet.dhcp.hosts if vnet.dhcp else []


def dns_hosts(conn, network):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(conn.networkLookupByName(network).XMLDesc())
    return sorted((h.get("ip"), n.text) for h in root.iterfind("dns/host") for n in h.iterfind("hostname"))


@pytest.mark.parametrize("active", [False, True])
def test_set_dhcp_host(host, conn, active):
    define_vnet(host, VNet("m", ip="10.9.0.254/24", devices=[]))  # no <dhcp> yet
    if active:
        conn.networkLookupByName("m").create()
    a = DHCPHost("c0:ff:ee:01:00:01", "10.9.0.1", "vm-01")
    set_dhcp_host(host, "m", a)
    set_dhcp_host(host, "m", a)  # unchanged: no duplicate
    assert leases(conn, "m") == [a]
    assert dns_hosts(conn, "m") == [("10.9.0.1", "vm-01")]  # name resolvable without network restart
    moved = DHCPHost("c0:ff:ee:01:00:01", "10.9.0.11", "vm-01")
    set_dhcp_host(host, "m", moved)  # same MAC: replaced
    assert leases(conn, "m") == [moved]
    assert dns_hosts(conn, "m") == [("10.9.0.11", "vm-01")]
    remove_dhcp_host(host, "m", "c0:ff:ee:01:00:01")
    remove_dhcp_host(host, "m", "c0:ff:ee:01:00:01")  # already gone: no error
    assert leases(conn, "m") == []
    assert dns_hosts(conn, "m") == []


def test_unnamed_lease_no_dns(host, conn):
    define_vnet(host, VNet("m", ip="10.9.0.254/24", devices=[]))
    set_dhcp_host(host, "m", DHCPHost("c0:ff:ee:01:00:01", "10.9.0.1"))
    assert dns_hosts(conn, "m") == []


def test_set_dhcp_host_unmanaged_untouched(host, conn, caplog):
    define_vnet(host, VNet("infra", ip="10.8.0.254/24"))
    set_dhcp_host(host, "infra", DHCPHost("c0:ff:ee:01:00:01", "10.8.0.1"))
    assert leases(conn, "infra") == []
    assert "not managed by vlab" in caplog.text


def test_delete_vms_removes_leases(host, conn):
    define_vnet(host, VNet("m", ip="10.9.0.254/24", devices=[], dhcp=DHCP(hosts=[DHCPHost("c0:ff:ee:09:00:09", "10.9.0.9")])))
    define_vm(host, VM("vm-01", interfaces=[Interface("network", "m", mac="c0:ff:ee:01:00:01")]))
    set_dhcp_host(host, "m", DHCPHost("c0:ff:ee:01:00:01", "10.9.0.1", "vm-01"))
    delete_vms(host, "vm-01")
    assert leases(conn, "m") == [DHCPHost("c0:ff:ee:09:00:09", "10.9.0.9")]  # other lease kept
