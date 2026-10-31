"""virt.api against a fake libvirt connection (no real libvirt calls)."""

import pytest

from vlab.node import Node
from vlab.virt import VM, VNet, api, define_vm, define_vnet


class FakeConn:
    def __init__(self, uri: str, fail: bool = False):
        self.uri, self.fail = uri, fail
        self.calls: list[tuple[str, str]] = []
        self.closed = False

    def _call(self, name: str, xml: str) -> None:
        self.calls.append((name, xml))
        if self.fail:
            raise RuntimeError("libvirt error")

    def defineXML(self, xml):
        self._call("defineXML", xml)

    def networkDefineXML(self, xml):
        self._call("networkDefineXML", xml)

    def close(self):
        self.closed = True


@pytest.fixture
def conns(monkeypatch):
    opened: list[FakeConn] = []

    def open_(uri):
        opened.append(FakeConn(uri))
        return opened[-1]

    monkeypatch.setattr(api.libvirt, "open", open_)
    return opened


def test_define_vm(conns):
    node, vm = Node(libvirt_uri="qemu+ssh://lab/system"), VM("vm-01")
    define_vm(node, vm)
    (conn,) = conns
    assert conn.uri == "qemu+ssh://lab/system"
    assert conn.calls == [("defineXML", vm.to_xml(node))]
    assert conn.closed


def test_define_vnet(conns):
    vnet = VNet("mgmt-1", ip="172.255.1.254/24", forward="nat")
    define_vnet(Node(), vnet)
    (conn,) = conns
    assert conn.uri == "qemu:///system"
    assert conn.calls == [("networkDefineXML", vnet.to_xml())]
    assert conn.closed


def test_connection_closed_on_error(monkeypatch):
    opened: list[FakeConn] = []
    monkeypatch.setattr(api.libvirt, "open", lambda uri: opened.append(FakeConn(uri, fail=True)) or opened[-1])
    with pytest.raises(RuntimeError):
        define_vnet(Node(), VNet("p2p-1"))
    assert opened[0].closed
