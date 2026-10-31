import sys

import pytest

from vlab import cli
from vlab.spec import Debian

from conftest import TOPOLOGY


def run_cli(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["vlab", *argv])
    cli.main()


def test_deploy(monkeypatch, capsys):
    deployed = []
    monkeypatch.setattr(Debian, "deploy", lambda self, node: deployed.append((self.name, node)))
    run_cli(monkeypatch, "deploy", "-f", str(TOPOLOGY / "test.yaml/vm-1.yaml"))
    assert [name for name, _ in deployed] == ["vm-01"]
    assert capsys.readouterr().out == "vm-01 defined\n"


def test_deploy_requires_file(monkeypatch):
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, "deploy")


def test_no_command(monkeypatch):
    with pytest.raises(SystemExit):
        run_cli(monkeypatch)
