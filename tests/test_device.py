"""spec.Device flow: libvirt via the in-memory test driver, host file operations recorded by FakeHost."""

from dataclasses import dataclass

import libvirt
import pytest

from vlab.spec import Device, delete
from vlab.virt import VM, VNet, Interface, define_vnet, list_vms, list_vnets

from conftest import FakeHost


@dataclass
class TwoVms(Device):
    """Device type with its own naming: <name>-a, <name>-b on an internal VNet."""

    def vms(self):
        net = [Interface("network", f"{self.name}-int")]
        return [VM(f"{self.name}-a", device=self.name, interfaces=net), VM(f"{self.name}-b", device=self.name, interfaces=net)]

    def vnets(self):
        return [VNet(f"{self.name}-int", devices=[self.name])]

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
    TwoVms(name="r1", id=1).deploy(host)
    assert {"r1-a", "r1-b"} <= set(names(list_vms(host)))
    vnets = {v.name: v for v, _ in list_vnets(host)}
    assert vnets["r1-int"].devices == ["r1"]
    assert ("mkdir", "-p", "/var/lib/vlab/vms/r1-a") in host.commands()
    assert {vm.device for vm, _ in list_vms(host) if vm.name.startswith("r1-")} == {"r1"}


def test_deploy_keeps_existing_vnet(host):
    define_vnet(host, VNet("r1-int", devices=["r1"], ip="10.0.0.1/24"))
    TwoVms(name="r1", id=1).deploy(host)
    assert {v.name: v for v, _ in list_vnets(host)}["r1-int"].ip == "10.0.0.1/24"


def test_start_stop(host):
    device = TwoVms(name="r1", id=1)
    device.deploy(host)
    device.start(host)
    assert all(active for vm, active in list_vms(host) if vm.device == "r1")
    assert dict((v.name, a) for v, a in list_vnets(host))["r1-int"]
    device.stop(host)
    assert not any(active for vm, active in list_vms(host) if vm.device == "r1")
    assert not dict((v.name, a) for v, a in list_vnets(host))["r1-int"]


@pytest.mark.parametrize("keep_files", [False, True])
def test_delete(keep_files):
    host = FakeHost(uri="test:///default", existing={"/var/lib/vlab/vms/r1-a", "/var/lib/vlab/vms/r1-b"})
    conn = libvirt.open(host.libvirt_uri)
    device = TwoVms(name="r1", id=1)
    device.deploy(host)
    host.calls.clear()
    device.delete(host, keep_files=keep_files)
    assert not [vm for vm, _ in list_vms(host) if vm.device == "r1"]
    rms = [c for c in host.commands() if c[0] == "rm"]
    assert rms == ([] if keep_files else [("rm", "-r", "/var/lib/vlab/vms/r1-a"), ("rm", "-r", "/var/lib/vlab/vms/r1-b")])
    conn.close()


def test_delete_missing_folder_skipped():
    host = FakeHost(uri="test:///default")
    conn = libvirt.open(host.libvirt_uri)
    TwoVms(name="r2", id=1).deploy(host)
    delete(host, "r2-a")
    assert not [c for c in host.commands() if c[0] == "rm"]
    conn.close()


def test_deploy_registers_dhcp_leases(host):
    from vlab.virt import DHCPHost

    @dataclass
    class WithLease(TwoVms):
        def dhcp_leases(self):
            return [(f"{self.name}-int", DHCPHost("c0:ff:ee:07:00:01", "10.7.0.1", self.name))]

        def vnets(self):
            return [VNet(f"{self.name}-int", ip="10.7.0.254/24", devices=[self.name])]

    WithLease(name="r7", id=7).deploy(host)
    vnet = {v.name: v for v, _ in list_vnets(host)}["r7-int"]
    assert vnet.dhcp.hosts == [DHCPHost("c0:ff:ee:07:00:01", "10.7.0.1", "r7")]


def test_from_dict_dispatch_by_type():
    from vlab.spec import Linux
    d = Device.from_dict({"type": "linux", "name": "vm-09", "id": 9, "user": "u"})
    assert isinstance(d, Linux) and (d.name, d.id) == ("vm-09", 9)


@pytest.mark.parametrize("data, err", [
    ({"name": "x", "id": 1, "user": "u"}, "missing"),
    ({"type": "router", "name": "x"}, "no subtype"),
])
def test_from_dict_type_required(data, err):
    with pytest.raises(Exception, match=err):
        Device.from_dict(data)
