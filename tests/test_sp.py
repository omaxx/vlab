"""topology/sp: SP lab from topology/topology.drawio - 10 vMX (P R1-R4, PE R5-R8, CE R10/R20), 22 p2p links."""

from ipaddress import IPv4Interface

import pytest

from vlab.spec import VMX, load_topology

from conftest import TOPOLOGY

ROUTERS = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R10", "R20"]


@pytest.fixture(scope="module")
def devices():
    return {d.name: d for d in load_topology(str(TOPOLOGY / "sp/topology.yaml")).devices}


def test_routers(devices):
    assert list(devices) == ROUTERS
    for name, d in devices.items():
        assert isinstance(d, VMX)
        assert d.id == int(name[1:])  # id = router number
        assert d.mgmt.ip == f"172.255.1.{d.id}/24"


def test_links_and_ips(devices):
    ends: dict[str, list[tuple[str, IPv4Interface]]] = {}
    for d in devices.values():
        ifaces = d.vars["interfaces"]
        assert list(ifaces) == [f"ge-0/0/{i}" for i in range(len(d.ports))]  # port N = ge-0/0/N
        for port, ifc in zip(d.ports, ifaces.values()):
            ip = IPv4Interface(ifc["ip"])
            assert int(ip.ip) & 0xFF == d.id  # .id on every link
            assert port.p2p is not None
            ends.setdefault(port.p2p, []).append((d.name, ip))
    assert len(ends) == 22
    num = {r: 9 if r in ("R10", "R20") else int(r[1:]) for r in ROUTERS}
    for link, ((a, ip_a), (b, ip_b)) in ((k, v) for k, v in ends.items() if len(v) == 2):
        assert link == f"{a}-{b}" or link == f"{b}-{a}"
        assert ip_a.network == ip_b.network == IPv4Interface(f"10.0.{min(num[a], num[b])}{max(num[a], num[b])}.0/24").network
    assert all(len(v) == 2 for v in ends.values())  # every link has exactly two ends


def test_loopbacks_and_rendered(devices):
    expected = {f"R{i}": f"10.0.0.{i}/32" for i in range(1, 9)} | {"R10": "10.10.0.1/32", "R20": "10.20.0.1/32"}
    assert {n: d.vars["loopback"] for n, d in devices.items()} == expected
    for d in devices.values():
        assert d.rendered_config is not None and f"address {d.vars['loopback']};" in d.rendered_config


def test_unique_macs_and_consoles(devices):
    macs = [i.mac for d in devices.values() for vm in d.vms() for i in vm.interfaces]
    assert len(macs) == len(set(macs))
    ports = [vm.telnet_port for d in devices.values() for vm in d.vms()]
    assert len(ports) == len(set(ports))
