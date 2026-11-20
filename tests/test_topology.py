"""topology/test.*: [srv-1] -- srv-1 -- [vmx-1] -- p2p-1/p2p-2 -- [vmx-2] -- srv-2 -- [srv-2] (+ mgmt-1)."""

from ipaddress import IPv4Interface

import pytest

from vlab.spec import VMX, Linux, Network, load_device, load_topology
from vlab.utils import load_file

from conftest import TOPOLOGY

DEVICES = ["srv-1", "vmx-1", "vmx-2", "srv-2"]
NETWORKS = ["mgmt-1", "srv-1", "p2p-1", "p2p-2", "srv-2"]


def yaml_topo():
    t = load_topology(str(TOPOLOGY / "test.yaml/topology.yaml"))
    mgmt = Network.from_dict(load_file(str(TOPOLOGY / "test.yaml/networks/mgmt.yaml")))
    return {d.name: d for d in t.devices}, {n.name: n for n in [mgmt, *t.networks]}


def jsonnet_topo():
    d = TOPOLOGY / "test.jsonnet"
    devices = {n: load_device(str(d / f"{n}.jsonnet")) for n in DEVICES}
    networks = {n: Network.from_dict(load_file(str(d / f"{n}.net.jsonnet"))) for n in NETWORKS}
    return devices, networks


@pytest.fixture(params=["yaml", "jsonnet"])
def topo(request):
    return yaml_topo() if request.param == "yaml" else jsonnet_topo()


def test_yaml_topology_equals_jsonnet_files():
    (yd, yn), (jd, jn) = yaml_topo(), jsonnet_topo()
    assert list(yd) == DEVICES and sorted(yn) == sorted(NETWORKS)
    for name in DEVICES:
        assert yd[name] == jd[name]
        assert getattr(yd[name], "rendered_config", None) == getattr(jd[name], "rendered_config", None)
    assert yn == jn


def test_links(topo):
    devices, networks = topo
    attached: dict[str, set[str]] = {n: set() for n in NETWORKS}
    for d in devices.values():
        for vm in d.vms():
            for net in vm.networks():
                if net in attached:
                    attached[net].add(d.name)
    assert attached["srv-1"] == {"srv-1", "vmx-1"}
    assert attached["p2p-1"] == attached["p2p-2"] == {"vmx-1", "vmx-2"}
    assert attached["srv-2"] == {"vmx-2", "srv-2"}
    assert attached["mgmt-1"] == set(DEVICES)
    for name in ("srv-1", "srv-2", "p2p-1", "p2p-2"):  # network spec owners = attached devices
        assert set(networks[name].devices) == attached[name]


def test_unique_ids_macs_consoles_mgmt_ips(topo):
    devices, _ = topo
    ids = [d.id for d in devices.values()]
    assert len(set(ids)) == len(ids)
    macs = [i.mac for d in devices.values() for vm in d.vms() for i in vm.interfaces]
    assert len(set(macs)) == len(macs)
    ports = [vm.telnet_port for d in devices.values() for vm in d.vms()]
    assert len(set(ports)) == len(ports)
    leases = [lease.ip for d in devices.values() for _, lease in d.dhcp_leases()]
    assert sorted(leases) == ["172.255.1.1", "172.255.1.2", "172.255.1.3", "172.255.1.5"]


def test_routing_is_symmetric(topo):
    """srv-1 -> vmx-1 -> vmx-2 -> srv-2 and back: every next hop is an address on the right device."""
    devices, _ = topo
    srv1, srv2 = devices["srv-1"], devices["srv-2"]
    vmx1, vmx2 = devices["vmx-1"], devices["vmx-2"]
    assert isinstance(srv1, Linux) and isinstance(srv2, Linux) and isinstance(vmx1, VMX) and isinstance(vmx2, VMX)

    def addrs(vmx):
        return {str(IPv4Interface(i["address"]).ip) for i in vmx.vars["interfaces"].values()}

    assert srv1.ports[1].routes == {"10.2.0.0/24": "10.1.0.1"} and "10.1.0.1" in addrs(vmx1)
    assert srv2.ports[1].routes == {"10.1.0.0/24": "10.2.0.1"} and "10.2.0.1" in addrs(vmx2)
    assert vmx1.vars["static_routes"] == {"10.2.0.0/24": "192.168.1.5"} and "192.168.1.5" in addrs(vmx2)
    assert vmx2.vars["static_routes"] == {"10.1.0.0/24": "192.168.1.3"} and "192.168.1.3" in addrs(vmx1)
    for vmx in (vmx1, vmx2):
        assert vmx.rendered_config is not None and "routing-options" in vmx.rendered_config


def write(tmp_path, text):
    p = tmp_path / "topology.yaml"
    p.write_text(text)
    return str(p)


def test_load_topology_names_from_keys(tmp_path):
    t = load_topology(write(tmp_path, "devices:\n  r1: {type: linux, id: 1, user: u}\nnetworks:\n  lan: {}\n"))
    assert [d.name for d in t.devices] == ["r1"] and [n.name for n in t.networks] == ["lan"]
    assert t.networks[0].devices == []


@pytest.mark.parametrize("text, err", [
    ("devices:\n  r1: {type: linux, name: r2, id: 1, user: u}\n", "differs from key"),
    ("devices: [a]\n", "must be a map"),
    ("routers: {}\n", "unknown top-level keys"),
])
def test_load_topology_errors(tmp_path, text, err):
    with pytest.raises(ValueError, match=err):
        load_topology(write(tmp_path, text))


def test_load_topology_resolves_configs_next_to_file(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/t.j2").write_text("host-name {{ device.name }};")
    t = load_topology(write(tmp_path, (
        "devices:\n  v1:\n    type: jnpr/vmx\n    id: 9\n    version: x\n    re_image: r\n    fpc_image: f\n"
        "    config: t.j2\n"
    )))
    assert t.devices[0].rendered_config == "host-name v1;"
