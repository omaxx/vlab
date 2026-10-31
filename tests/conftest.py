from pathlib import Path
import shutil
import subprocess

import pytest

from vlab.host import Host

TOPOLOGY = Path(__file__).parent.parent / "topology"


class FakeHost(Host):
    """Host that records commands instead of running them; `files` serves `cat`, `existing` answers `test -e`."""

    def __init__(self, files: dict[str, str] | None = None, existing: set[str] | None = None, **kw):
        super().__init__(**kw)
        self.files = files or {}
        self.existing = existing or set()
        self.calls: list[tuple[tuple[str, ...], str | None]] = []

    def _proc(self, cmd, input, check):
        self.calls.append((cmd, input))
        stdout = self.files.get(cmd[1], "") if cmd[0] == "cat" else ""
        rc = 0 if cmd[:2] != ("test", "-e") or cmd[2] in self.existing else 1
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
