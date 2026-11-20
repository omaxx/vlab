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
        assert d.vars["interfaces"]["fxp0"]["ip"] == f"172.255.1.{d.id}/24"  # fxp0 static, set by the config
        assert (d.version, d.re_image, d.fpc_image) == (
            "24.4R1-S2.9", "junos-vmx-x86-64-24.4R1-S2.9.qcow2", "vFPC-20241118.img",
        )
        assert d.dhcp_leases() == []  # static mgmt, no dhcp


def test_links_and_ips(devices):
    ends: dict[str, list[tuple[str, IPv4Interface]]] = {}
    for d in devices.values():
        names = [f"ge-0/0/{i}" for i in range(len(d.ports))]  # port N = ge-0/0/N
        assert set(d.vars["interfaces"]) == {"fxp0", "lo0", *names}  # jsonnet vars: keys come sorted, order not checked
        for port, ifc in zip(d.ports, (d.vars["interfaces"][n] for n in names)):
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


def test_interface_families(devices):
    """ip/ipv6/iso/mpls -> family inet/inet6/iso/mpls: address -> `family X { address A; }`, true -> `family X;`."""
    from vlab.spec.jnpr import render_template
    d = devices["R1"]
    interfaces = {
        "ge-0/0/0": {"ip": "10.0.13.1/24", "ipv6": "2001:db8::1/64", "iso": True, "mpls": True},
        "ge-0/0/1": {"ip": True, "ipv6": False},  # false = no family
        "lo0": {"ip": "10.0.0.1/32", "iso": "49.0001.0100.0000.0001.00"},
    }
    cfg = render_template("vmx.conf.j2", str(TOPOLOGY / "sp"), device=d, **{**d.vars, "interfaces": interfaces})
    assert """    ge-0/0/0 {
        unit 0 {
            family inet {
                address 10.0.13.1/24;
            }
            family inet6 {
                address 2001:db8::1/64;
            }
            family iso;
            family mpls;
        }
    }
    ge-0/0/1 {
        unit 0 {
            family inet;
        }
    }
    lo0 {
        unit 0 {
            family inet {
                address 10.0.0.1/32;
            }
            family iso {
                address 49.0001.0100.0000.0001.00;
            }
        }
    }
""" in cfg
    assert "dhcp" not in cfg


AREAS = {"R1": "49.0001", "R2": "49.0001", "R5": "49.0001", "R6": "49.0001",
         "R3": "49.0002", "R4": "49.0002", "R7": "49.0002", "R8": "49.0002"}  # R10/R20 (CE): no ISO


def test_iso(devices):
    """lo0 NET = area + loopback ip padded to 12 digits; lo0 ipv6 fd00::<id>/128;
    family inet6 (no address) + iso + mpls on links whose both ends are in AREAS."""
    for n, d in devices.items():
        ifs = d.vars["interfaces"]
        if n in AREAS:
            digits = "".join(f"{int(o):03d}" for o in ifs["lo0"]["ip"].split("/")[0].split("."))
            assert ifs["lo0"]["iso"] == f"{AREAS[n]}.{digits[:4]}.{digits[4:8]}.{digits[8:]}.00"
            assert f"family iso {{\n                address {ifs['lo0']['iso']};" in d.rendered_config
            assert ifs["lo0"]["ipv6"] == f"fd00::{d.id}/128"
        else:
            assert "iso" not in ifs["lo0"] and "ipv6" not in ifs["lo0"]
        for name, ifc in ifs.items():
            if name.startswith("ge-"):
                peer = ifc["description"].split()[1]
                core = n in AREAS and peer in AREAS
                assert ifc.get("iso", False) is core, (n, name)
                assert ifc.get("mpls", False) is core, (n, name)
                assert ifc.get("ipv6", False) is core, (n, name)


def test_lldp(devices):
    """LLDP on all interfaces except fxp0 (mgmt)."""
    lldp = "protocols {\n    lldp {\n        interface all;\n        interface fxp0 {\n            disable;\n        }\n    }\n"
    for d in devices.values():
        assert d.rendered_config is not None and lldp in d.rendered_config, d.name


def test_protocols_mpls(devices):
    """protocols mpls: an interface line for each interface with mpls: true; no mpls section without any."""
    for d in devices.values():
        names = [n for n, ifc in d.vars["interfaces"].items() if ifc.get("mpls") is True]
        cfg = d.rendered_config
        assert cfg is not None
        if names:
            lines = "".join(f"        interface {n};\n" for n in names)
            assert f"    mpls {{\n{lines}    }}\n}}\n" in cfg, d.name
        else:
            assert "    mpls {" not in cfg, d.name
    assert len([n for n, i in devices["R1"].vars["interfaces"].items() if i.get("mpls")]) == 5
