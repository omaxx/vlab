import logging

from click.testing import CliRunner
import pytest

from vlab import cli, spec, virt
from vlab.host import Host
from vlab.spec import Linux, Network
from vlab.virt import VM

from conftest import TOPOLOGY


def invoke(*args):
    return CliRunner().invoke(cli.main, list(args))


@pytest.fixture
def recorded(monkeypatch):
    """Replace libvirt-facing functions used by the CLI; return recorded calls."""
    calls = []
    vms = [(VM("r1", device="r1"), True), (VM("r2", device="r2"), False), (VM("other"), False)]
    monkeypatch.setattr(virt, "list_vms", lambda host: vms)
    monkeypatch.setattr(virt, "start_vms", lambda host, *n: calls.append(("start", n)))
    monkeypatch.setattr(virt, "stop_vms", lambda host, *n, force, timeout: calls.append(("stop", n)))
    monkeypatch.setattr(spec, "delete", lambda host, *n, keep_files: calls.append(("delete", n, keep_files)))
    return calls


@pytest.mark.parametrize("overwrite", [False, True])
def test_deploy(monkeypatch, overwrite):
    deployed = []
    monkeypatch.setattr(Linux, "deploy", lambda self, host, overwrite: deployed.append((self.name, host, overwrite)))
    args = ["deploy", "-d", str(TOPOLOGY / "test.jsonnet/srv-1.jsonnet")] + (["--overwrite"] if overwrite else [])
    r = invoke(*args)
    assert r.exit_code == 0, r.output
    assert deployed == [("srv-1", Host(), overwrite)]
    assert r.output == "device srv-1 deployed\n"


def test_deploy_networks_before_devices(monkeypatch):
    order = []
    monkeypatch.setattr(Linux, "deploy", lambda self, host, overwrite: order.append(self.name))
    monkeypatch.setattr(Network, "deploy", lambda self, host: order.append(self.name))
    r = invoke(
        "deploy",
        "-d", str(TOPOLOGY / "test.jsonnet/srv-1.jsonnet"),
        "-d", str(TOPOLOGY / "test.jsonnet/srv-2.jsonnet"),
        "-n", str(TOPOLOGY / "test.jsonnet/mgmt-1.net.jsonnet"),
    )
    assert r.exit_code == 0, r.output
    assert order == ["mgmt-1", "srv-1", "srv-2"]


def test_deploy_topology(monkeypatch):
    from vlab.spec import VMX, Linux
    order = []
    for cls in (Linux, VMX):
        monkeypatch.setattr(cls, "deploy", lambda self, host, overwrite: order.append(("device", self.name, overwrite)))
    monkeypatch.setattr(Network, "deploy", lambda self, host: order.append(("network", self.name)))
    r = invoke(
        "deploy",
        "-t", str(TOPOLOGY / "test.yaml/topology.yaml"),
        "-n", str(TOPOLOGY / "test.yaml/networks/mgmt.yaml"),
        "-d", str(TOPOLOGY / "test.jsonnet/srv-1.jsonnet"),
        "--overwrite",
    )
    assert r.exit_code == 0, r.output
    assert order == [  # all networks (topology has none now, then -n) before all devices (topology, then -d)
        ("network", "mgmt-1"),
        ("device", "srv-1", True), ("device", "vmx-1", True), ("device", "vmx-2", True), ("device", "srv-2", True),
        ("device", "srv-1", True),
    ]


def test_deploy_bad_spec_fails_before_changes(monkeypatch, tmp_path):
    deployed = []
    monkeypatch.setattr(Network, "deploy", lambda self, host: deployed.append(self.name))
    bad = tmp_path / "bad.yaml"
    bad.write_text("type: router\nname: x\nid: 1\n")
    r = invoke("deploy", "-n", str(TOPOLOGY / "test.yaml/networks/mgmt.yaml"), "-d", str(bad))
    assert r.exit_code != 0
    assert deployed == []  # mgmt-1 not deployed: all specs load before any change


def test_deploy_requires_spec():
    r = invoke("deploy")
    assert r.exit_code == 2
    assert "give -t TOPOLOGY_FILE, -d DEVICE_FILE and/or -n NETWORK_FILE" in r.output


def test_deploy_missing_file(tmp_path):
    r = invoke("deploy", "-n", str(tmp_path / "nope.yaml"))
    assert r.exit_code == 2
    assert "does not exist" in r.output


def test_no_command():
    r = invoke()
    assert r.exit_code == 2
    assert "deploy" in r.output


@pytest.mark.parametrize(
    "args, expected",
    [
        (["vm-x"], ("vm-x",)),
        (["-d", "r2"], ("r2",)),
        (["--device", "r1", "--device", "r2"], ("r1", "r2")),
        (["--all"], ("r1", "r2")),  # only VMs with vlab metadata
        (["r1", "-d", "r1"], ("r1",)),  # no duplicates
    ],
)
def test_vm_selection(recorded, args, expected):
    assert invoke("start", *args).exit_code == 0
    assert invoke("stop", *args).exit_code == 0
    assert recorded == [("start", expected), ("stop", expected)]


def test_selection_required(recorded):
    r = invoke("start")
    assert r.exit_code == 2
    assert "give VM names, --device or --all" in r.output


@pytest.mark.parametrize("flag, keep", [([], False), (["--keep-files"], True)])
def test_delete(recorded, flag, keep):
    assert invoke("delete", "-d", "r1", *flag).exit_code == 0
    assert recorded == [("delete", ("r1",), keep)]


@pytest.mark.parametrize("flags, level", [([], logging.WARNING), (["-v"], logging.INFO), (["-vv"], logging.DEBUG), (["-vvv"], logging.DEBUG)])
def test_verbosity(monkeypatch, flags, level):
    seen = {}
    monkeypatch.setattr(cli.logging, "basicConfig", lambda **kw: seen.update(kw))
    monkeypatch.setattr(virt, "list_vms", lambda host: [])
    assert invoke(*flags, "list", "vms").exit_code == 0
    assert seen["level"] == level


def test_list(monkeypatch):
    from vlab.virt import Disk, Interface, VNet
    monkeypatch.setattr(virt, "list_vms", lambda host: [(VM("r1", device="r1", interfaces=[Interface("bridge", "br0")], disks=[Disk("/d.qcow2", "vda")]), True)])
    monkeypatch.setattr(virt, "list_vnets", lambda host: [(VNet("mgmt-1", ip="172.255.1.254/24", forward="nat"), True)])
    r = invoke("list", "vms")
    assert r.exit_code == 0 and "r1" in r.output and "bridge(br0)" in r.output and "/d.qcow2" in r.output
    r = invoke("list", "vnets")
    assert r.exit_code == 0 and "mgmt-1" in r.output and "nat" in r.output
