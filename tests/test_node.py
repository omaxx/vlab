"""Node operations run real processes, confined to tmp_path."""

import shutil
import subprocess

import pytest

from vlab.node import Node


@pytest.fixture
def node(tmp_path):
    return Node(vm_path=str(tmp_path))


def test_paths():
    n = Node()
    assert n.images_dir == "/var/lib/vlab/images"
    assert n.vm_dir("vm-01") == "/var/lib/vlab/vms/vm-01"


def test_mkdir_exists_rm(node, tmp_path):
    d = f"{tmp_path}/a/b"
    assert not node.exists(d)
    node.mkdir(d)
    node.mkdir(d)  # idempotent
    assert node.exists(d)
    node.rm(f"{tmp_path}/a")
    assert not node.exists(d)


def test_write_read_cp(node, tmp_path):
    src, dst = f"{tmp_path}/src", f"{tmp_path}/dst"
    content = "line 1\nquote ' \" $HOME `x`\n"
    node.write(src, content)
    assert node.read(src) == content
    node.cp(src, dst)
    assert node.read(dst) == content


def test_run_error(node):
    with pytest.raises(subprocess.CalledProcessError):
        node.read("/nonexistent/file")


@pytest.mark.skipif(not shutil.which("qemu-img"), reason="qemu-img not installed")
def test_cow_and_resize(node, tmp_path):
    base, overlay = f"{tmp_path}/base.qcow2", f"{tmp_path}/overlay.qcow2"
    node.run("qemu-img", "create", "-f", "qcow2", base, "1G")
    node.cow(base, overlay)
    info = node.run("qemu-img", "info", overlay)
    assert f"backing file: {base}" in info
    node.resize(overlay, "2G")
    assert "virtual size: 2 GiB" in node.run("qemu-img", "info", overlay)


@pytest.mark.skipif(not shutil.which("cloud-localds"), reason="cloud-localds not installed")
@pytest.mark.parametrize("with_net", [True, False])
def test_seed_iso(node, tmp_path, with_net):
    node.write(f"{tmp_path}/user-data", "#cloud-config\n{}\n")
    node.write(f"{tmp_path}/meta-data", "{}\n")
    node.write(f"{tmp_path}/network-config", "{\"version\": 2}\n")
    net = f"{tmp_path}/network-config" if with_net else None
    node.seed_iso(f"{tmp_path}/seed.iso", f"{tmp_path}/user-data", f"{tmp_path}/meta-data", net)
    assert node.exists(f"{tmp_path}/seed.iso")
