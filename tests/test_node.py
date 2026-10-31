"""spec.Node flow: libvirt via the in-memory test driver, host file operations recorded by FakeHost."""

from dataclasses import dataclass

import libvirt
import pytest

from vlab.spec import Node, delete
from vlab.virt import VM, VNet, Interface, define_vnet, list_vms, list_vnets

from conftest import FakeHost


@dataclass
class TwoVms(Node):
    """Node type with its own naming: <name>-a, <name>-b on an internal VNet."""

    def vms(self):
        net = [Interface(network=f"{self.name}-int")]
        return [VM(f"{self.name}-a", node=self.name, interfaces=net), VM(f"{self.name}-b", node=self.name, interfaces=net)]

    def vnets(self):
        return [VNet(f"{self.name}-int", nodes=[self.name])]

    def prepare(self, host, overwrite):
        for vm in self.vms():
            host.mkdir(host.vm_dir(vm.name))


@pytest.fixture
def host():
    h = FakeHost(uri="test:///default")
    conn = libvirt.open(h.libvirt_uri)  # keep test driver state alive
    yield h
    conn.close()


def names(items):
    return sorted(x.name for x, _ in items)


def test_deploy(host):
    TwoVms("r1").deploy(host)
    assert {"r1-a", "r1-b"} <= set(names(list_vms(host)))
    vnets = {v.name: v for v, _ in list_vnets(host)}
    assert vnets["r1-int"].nodes == ["r1"]
    assert ("mkdir", "-p", "/var/lib/vlab/vms/r1-a") in host.commands()
    assert {vm.node for vm, _ in list_vms(host) if vm.name.startswith("r1-")} == {"r1"}


def test_deploy_keeps_existing_vnet(host):
    define_vnet(host, VNet("r1-int", nodes=["r1"], ip="10.0.0.1/24"))
    TwoVms("r1").deploy(host)
    assert {v.name: v for v, _ in list_vnets(host)}["r1-int"].ip == "10.0.0.1/24"


def test_start_stop(host):
    node = TwoVms("r1")
    node.deploy(host)
    node.start(host)
    assert all(active for vm, active in list_vms(host) if vm.node == "r1")
    assert dict((v.name, a) for v, a in list_vnets(host))["r1-int"]
    node.stop(host)
    assert not any(active for vm, active in list_vms(host) if vm.node == "r1")
    assert not dict((v.name, a) for v, a in list_vnets(host))["r1-int"]


@pytest.mark.parametrize("keep_files", [False, True])
def test_delete(keep_files):
    host = FakeHost(uri="test:///default", existing={"/var/lib/vlab/vms/r1-a", "/var/lib/vlab/vms/r1-b"})
    conn = libvirt.open(host.libvirt_uri)
    node = TwoVms("r1")
    node.deploy(host)
    host.calls.clear()
    node.delete(host, keep_files=keep_files)
    assert not [vm for vm, _ in list_vms(host) if vm.node == "r1"]
    rms = [c for c in host.commands() if c[0] == "rm"]
    assert rms == ([] if keep_files else [("rm", "-r", "/var/lib/vlab/vms/r1-a"), ("rm", "-r", "/var/lib/vlab/vms/r1-b")])
    conn.close()


def test_delete_missing_folder_skipped():
    host = FakeHost(uri="test:///default")
    conn = libvirt.open(host.libvirt_uri)
    TwoVms("r2").deploy(host)
    delete(host, "r2-a")
    assert not [c for c in host.commands() if c[0] == "rm"]
    conn.close()
