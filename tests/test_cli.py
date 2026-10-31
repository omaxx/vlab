from click.testing import CliRunner

from vlab import cli
from vlab.spec import Debian

from conftest import TOPOLOGY


def test_deploy(monkeypatch):
    deployed = []
    monkeypatch.setattr(Debian, "deploy", lambda self, node: deployed.append((self.name, node)))
    r = CliRunner().invoke(cli.main, ["deploy", "-f", str(TOPOLOGY / "test.yaml/vm-1.yaml")])
    assert r.exit_code == 0, r.output
    assert [name for name, _ in deployed] == ["vm-01"]
    assert r.output == "vm-01 defined\n"


def test_deploy_requires_file():
    r = CliRunner().invoke(cli.main, ["deploy"])
    assert r.exit_code == 2
    assert "Missing option '-f'" in r.output


def test_deploy_missing_file(tmp_path):
    r = CliRunner().invoke(cli.main, ["deploy", "-f", str(tmp_path / "nope.yaml")])
    assert r.exit_code == 2
    assert "does not exist" in r.output


def test_no_command():
    r = CliRunner().invoke(cli.main, [])
    assert r.exit_code == 2
    assert "deploy" in r.output
