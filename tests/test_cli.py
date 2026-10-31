import logging

from click.testing import CliRunner
import pytest

from vlab import cli, spec, virt
from vlab.host import Host
from vlab.spec import Debian, Network
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
    monkeypatch.setattr(virt, "stop_vms", lambda host, *n: calls.append(("stop", n)))
    monkeypatch.setattr(spec, "delete", lambda host, *n, keep_files: calls.append(("delete", n, keep_files)))
    return calls


@pytest.mark.parametrize("overwrite", [False, True])
def test_deploy(monkeypatch, overwrite):
    deployed = []
    monkeypatch.setattr(Debian, "deploy", lambda self, host, overwrite: deployed.append((self.name, host, overwrite)))
    args = ["deploy", "-d", str(TOPOLOGY / "test.yaml/vm-1.yaml")] + (["--overwrite"] if overwrite else [])
    r = invoke(*args)
    assert r.exit_code == 0, r.output
    assert deployed == [("vm-01", Host(), overwrite)]
    assert r.output == "device vm-01 deployed\n"


def test_deploy_networks_before_devices(monkeypatch):
    order = []
    monkeypatch.setattr(Debian, "deploy", lambda self, host, overwrite: order.append(self.name))
    monkeypatch.setattr(Network, "deploy", lambda self, host: order.append(self.name))
    r = invoke(
        "deploy",
        "-d", str(TOPOLOGY / "test.yaml/vm-1.yaml"),
        "-d", str(TOPOLOGY / "test.jsonnet/vm-2.jsonnet"),
        "-n", str(TOPOLOGY / "test.jsonnet/mgmt-1.jsonnet"),
    )
    assert r.exit_code == 0, r.output
    assert order == ["mgmt-1", "vm-01", "vm-02"]


def test_deploy_requires_spec():
    r = invoke("deploy")
    assert r.exit_code == 2
    assert "give -d DEVICE_FILE and/or -n NETWORK_FILE" in r.output


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
    from vlab.virt import Interface, VNet
    monkeypatch.setattr(virt, "list_vms", lambda host: [(VM("r1", device="r1", interfaces=[Interface(bridge="br0")], disks=["/d.qcow2"]), True)])
    monkeypatch.setattr(virt, "list_vnets", lambda host: [(VNet("mgmt-1", ip="172.255.1.254/24", forward="nat"), True)])
    r = invoke("list", "vms")
    assert r.exit_code == 0 and "r1" in r.output and "br(br0)" in r.output and "/d.qcow2" in r.output
    r = invoke("list", "vnets")
    assert r.exit_code == 0 and "mgmt-1" in r.output and "nat" in r.output
