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
        assert (d.mgmt.network, d.mgmt.ip, d.mgmt.dhcp) == ("mgmt-1", None, False)  # whole mgmt port from the anchor
        assert d.vars["mgmt_ip"] == f"172.255.1.{d.id}/24"  # fxp0 static, set by the config
        assert (d.version, d.re_image, d.fpc_image) == (
            "24.4R1-S2.9", "junos-vmx-x86-64-24.4R1-S2.9.qcow2", "vFPC-20241118.img",
        )
        assert d.dhcp_leases() == []  # static mgmt, no dhcp


def test_links_and_ips(devices):
    ends: dict[str, list[tuple[str, IPv4Interface]]] = {}
    for d in devices.values():
        ifaces = {k: v for k, v in d.vars["interfaces"].items() if k != "lo0"}
        assert list(d.vars["interfaces"]) == ["lo0", *(f"ge-0/0/{i}" for i in range(len(d.ports)))]  # port N = ge-0/0/N
        for port, ifc in zip(d.ports, ifaces.values()):
            ip = IPv4Interface(ifc["ip"])
            assert int(ip.ip) & 0xFF == d.id  # .id on every link
            assert port.p2p is not None
            ends.setdefault(port.p2p, []).append((d.name, ip))
    assert len(ends) == 22
    num = {r: 9 if r in ("R10", "R20") else int(r[1:]) for r in ROUTERS}
    for link, ((a, ip_a), (b, ip_b)) in ((k, v) for k, v in ends.items() if len(v) == 2):
        assert link == f"{a}_{b}" or link == f"{b}_{a}"
        assert ip_a.network == ip_b.network == IPv4Interface(f"10.0.{min(num[a], num[b])}{max(num[a], num[b])}.0/24").network
    assert all(len(v) == 2 for v in ends.values())  # every link has exactly two ends


def test_loopbacks_and_rendered(devices):
    expected = {f"R{i}": f"10.0.0.{i}/32" for i in range(1, 9)} | {"R10": "10.10.0.1/32", "R20": "10.20.0.1/32"}
    assert {n: d.vars["interfaces"]["lo0"]["ip"] for n, d in devices.items()} == expected
    for n, d in devices.items():
        cfg = d.rendered_config
        assert cfg is not None and f"    lo0 {{\n        unit 0 {{\n            family inet {{\n                address {expected[n]};" in cfg


def test_unique_macs_and_consoles(devices):
    macs = [i.mac for d in devices.values() for vm in d.vms() for i in vm.interfaces]
    assert len(macs) == len(set(macs))
    ports = [vm.telnet_port for d in devices.values() for vm in d.vms()]
    assert len(ports) == len(set(ports))


def test_descriptions_point_to_peer_port(devices):
    ends: dict[str, list[tuple[str, str]]] = {}
    for d in devices.values():
        for i, port in enumerate(d.ports):
            assert port.p2p is not None
            ends.setdefault(port.p2p, []).append((d.name, f"ge-0/0/{i}"))
    for (a, pa), (b, pb) in ends.values():
        assert devices[a].vars["interfaces"][pa]["description"] == f"-> {b} : {pb}"
        assert devices[b].vars["interfaces"][pb]["description"] == f"-> {a} : {pa}"
        cfg = devices[a].rendered_config
        assert cfg is not None and f'description "-> {b} : {pb}";' in cfg


def test_users(devices):
    for d in devices.values():
        v = d.vars
        assert v["user_name"] == "maxim"
        assert v["root_pass"].startswith("$6$") and v["user_pass"].startswith("$6$")
        cfg = d.rendered_config
        assert cfg is not None
        assert f'root-authentication {{\n        encrypted-password "{v["root_pass"]}";' in cfg
        assert "user maxim {\n            class super-user;" in cfg
        assert f'encrypted-password "{v["user_pass"]}";' in cfg
        keys = [k for k in v["user_key"].splitlines() if k.strip()]
        assert keys
        for key in keys:
            kind = {"ssh-rsa": "ssh-rsa", "ssh-ed25519": "ssh-ed25519"}.get(key.split()[0], "ssh-ecdsa")
            assert f'{kind} "{key}";' in cfg
