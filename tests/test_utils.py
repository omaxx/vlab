import json

import pytest

from vlab.spec import Linux
from vlab.utils import load_file

from conftest import TOPOLOGY, yaml_spec

DATA = {"id": 1, "user": "u", "ports": [{"network": "mgmt-1", "ip": "172.255.1.1/24"}]}


def test_yaml(tmp_path):
    for ext in ("yaml", "yml"):
        f = tmp_path / f"spec.{ext}"
        f.write_text("id: 1\nuser: u\nports:\n  - network: mgmt-1\n    ip: 172.255.1.1/24\n")
        assert load_file(str(f)) == DATA


def test_json(tmp_path):
    f = tmp_path / "spec.json"
    f.write_text(json.dumps(DATA))
    assert load_file(str(f)) == DATA


def test_jsonnet_with_import(tmp_path):
    (tmp_path / "lib.libsonnet").write_text("{ vm(id):: { id: id, user: 'u', ports: [{ network: 'mgmt-1', ip: '172.255.1.%d/24' % id }] } }")
    f = tmp_path / "spec.jsonnet"
    f.write_text("(import 'lib.libsonnet').vm(1)")
    assert load_file(str(f)) == DATA


def test_unsupported(tmp_path):
    with pytest.raises(ValueError, match="unsupported"):
        load_file(str(tmp_path / "spec.toml"))


@pytest.mark.parametrize("n", [1, 2])
def test_topology_yaml_and_jsonnet_match(n):
    y = yaml_spec(f"srv-{n}")
    j = Linux.from_dict(load_file(str(TOPOLOGY / f"test.jsonnet/srv-{n}.jsonnet")))
    assert y == j
    assert y.name == f"srv-{n}"
    assert [(p.network, p.ip) for p in y.ports] == [("mgmt-1", f"172.255.1.{n}/24"), (f"srv-{n}", f"10.{n}.0.10/24")]


@pytest.mark.parametrize("ext, text", [("yaml", "- a\n- b\n"), ("json", "[1]"), ("jsonnet", "'x'"), ("yaml", "")])
def test_not_a_mapping(tmp_path, ext, text):
    f = tmp_path / f"spec.{ext}"
    f.write_text(text)
    with pytest.raises(ValueError, match="spec must be a mapping"):
        load_file(str(f))
