"""Host operations run real processes, confined to tmp_path."""

import shutil
import subprocess

import pytest

from vlab.host import Host


@pytest.fixture
def host(tmp_path):
    return Host(vm_path=str(tmp_path))


def test_paths():
    n = Host()
    assert n.images_dir == "/var/lib/vlab/images"
    assert n.vm_dir("vm-01") == "/var/lib/vlab/vms/vm-01"


def test_mkdir_exists_rm(host, tmp_path):
    d = f"{tmp_path}/a/b"
    assert not host.exists(d)
    host.mkdir(d)
    host.mkdir(d)  # idempotent
    assert host.exists(d)
    host.rm(f"{tmp_path}/a")
    assert not host.exists(d)


def test_write_read_cp(host, tmp_path):
    src, dst = f"{tmp_path}/src", f"{tmp_path}/dst"
    content = "line 1\nquote ' \" $HOME `x`\n"
    host.write(src, content)
    assert host.read(src) == content
    host.cp(src, dst)
    assert host.read(dst) == content


def test_run_error(host):
    with pytest.raises(subprocess.CalledProcessError):
        host.read("/nonexistent/file")


@pytest.mark.skipif(not shutil.which("qemu-img"), reason="qemu-img not installed")
def test_cow_and_resize(host, tmp_path):
    base, overlay = f"{tmp_path}/base.qcow2", f"{tmp_path}/overlay.qcow2"
    host.run("qemu-img", "create", "-f", "qcow2", base, "1G")
    host.cow(base, overlay)
    info = host.run("qemu-img", "info", overlay)
    assert f"backing file: {base}" in info
    host.resize(overlay, "2G")
    assert "virtual size: 2 GiB" in host.run("qemu-img", "info", overlay)


@pytest.mark.skipif(not shutil.which("cloud-localds"), reason="cloud-localds not installed")
@pytest.mark.parametrize("with_net", [True, False])
def test_seed_iso(host, tmp_path, with_net):
    host.write(f"{tmp_path}/user-data", "#cloud-config\n{}\n")
    host.write(f"{tmp_path}/meta-data", "{}\n")
    host.write(f"{tmp_path}/network-config", "{\"version\": 2}\n")
    net = f"{tmp_path}/network-config" if with_net else None
    host.seed_iso(f"{tmp_path}/seed.iso", f"{tmp_path}/user-data", f"{tmp_path}/meta-data", net)
    assert host.exists(f"{tmp_path}/seed.iso")


def test_libvirt_uri():
    assert Host().libvirt_uri == "qemu:///system"
    assert Host(ip="10.0.0.5").libvirt_uri == "qemu+ssh://10.0.0.5/system"
    assert Host(ip="10.0.0.5", uri="test:///default").libvirt_uri == "test:///default"
    assert str(Host()) == "localhost"
    assert str(Host(ip="10.0.0.5")) == "10.0.0.5"
