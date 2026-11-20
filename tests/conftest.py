from pathlib import Path
import shutil
import subprocess

import pytest

from vlab.host import Host

TOPOLOGY = Path(__file__).parent.parent / "topology"


def yaml_spec(name: str, kind: str = "devices"):
    """Device or network spec by name from topology/test.yaml/topology.yaml."""
    from vlab.spec import load_topology
    topo = load_topology(str(TOPOLOGY / "test.yaml/topology.yaml"))
    return {x.name: x for x in getattr(topo, kind)}[name]


class FakeHost(Host):
    """Host that records commands instead of running them.

    `files` serves `cat`, `existing` answers `test -e`, `env` answers `printenv`.
    """

    def __init__(self, files=None, existing=None, env=None, **kw):
        super().__init__(**kw)
        self.files: dict[str, str] = files or {}
        self.existing: set[str] = existing or set()
        self.env: dict[str, str] = {"HOME": "/home/test", "USER": "test"} if env is None else env
        self.calls: list[tuple[tuple[str, ...], str | None]] = []

    def _proc(self, cmd, input, check):
        self.calls.append((cmd, input))
        rc, stdout = 0, ""
        if cmd[0] == "cat":
            stdout = self.files.get(cmd[1], "")
        elif cmd[:2] == ("test", "-e"):
            rc = 0 if cmd[2] in self.existing else 1
        elif cmd[0] == "printenv":
            rc, stdout = (0, self.env[cmd[1]] + "\n") if cmd[1] in self.env else (1, "")
        return subprocess.CompletedProcess(cmd, rc, stdout, "")

    def commands(self) -> list[tuple[str, ...]]:
        return [c for c, _ in self.calls]


@pytest.fixture
def validate_xml():
    """Validate XML string against libvirt schema (skip if virt-xml-validate missing)."""
    if not shutil.which("virt-xml-validate"):
        pytest.skip("virt-xml-validate not installed")

    def check(xml: str, schema: str, tmp_path: Path) -> None:
        f = tmp_path / f"{schema}.xml"
        f.write_text(xml)
        r = subprocess.run(["virt-xml-validate", str(f), schema], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    return check
