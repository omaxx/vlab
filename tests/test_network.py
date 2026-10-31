"""spec.Network -> virt.VNet, deploy via libvirt's in-memory test driver."""

import libvirt
import pytest

from vlab.host import Host
from vlab.spec import Network
from vlab.utils import load_file
from vlab.virt import VNet, define_vnet, list_vnets

from conftest import TOPOLOGY


@pytest.fixture
def host():
    h = Host(uri="test:///default")
    conn = libvirt.open(h.libvirt_uri)  # keep test driver state alive
    yield h
    conn.close()


def test_vnets():
    n = Network("mgmt-1", ip="172.255.1.254/24", forward="nat")
    assert n.vnets() == [VNet("mgmt-1", None, "172.255.1.254/24", "nat", devices=[])]
    assert n.vnets()[0].managed
    assert Network("link-12", devices=["r1", "r2"]).vnets()[0].devices == ["r1", "r2"]


def test_deploy(host):
    Network("mgmt-1", ip="172.255.1.254/24", forward="nat").deploy(host)
    (vnet, active), = [(v, a) for v, a in list_vnets(host) if v.name == "mgmt-1"]
    assert not active
    assert (vnet.ip, vnet.forward, vnet.devices) == ("172.255.1.254/24", "nat", [])


def test_deploy_existing_kept(host):
    define_vnet(host, VNet("mgmt-1"))  # created outside vlab
    Network("mgmt-1", ip="172.255.1.254/24", forward="nat").deploy(host)
    (vnet,) = [v for v, _ in list_vnets(host) if v.name == "mgmt-1"]
    assert (vnet.ip, vnet.devices) == (None, None)


@pytest.mark.parametrize("ext", ["yaml", "jsonnet"])
def test_topology_mgmt(ext):
    n = Network.from_dict(load_file(str(TOPOLOGY / f"test.{ext}/mgmt-1.{ext}")))
    assert n == Network("mgmt-1", ip="172.255.1.254/24", forward="nat")
