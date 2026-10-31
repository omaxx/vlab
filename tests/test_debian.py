import json

import pytest
import yaml

from vlab.spec import Debian, Port

from conftest import FakeHost

VM_DIR = "/var/lib/vlab/vms/r3"


def make(**kw) -> Debian:
    return Debian(
        name="r3",
        id=3,
        user="omaxx",
        ports=[
            Port("mgmt-1", "172.255.1.3/24", gateway="172.255.1.254", dns=["172.255.1.254"]),
            Port("p2p-1", "192.168.1.3/24"),
            Port(bridge="br0"),
        ],
        **kw,
    )


def test_mac():
    assert make().mac(1) == "c0:ff:ee:03:00:01"
    assert Debian(name="x", id=12, user="u").mac(3) == "c0:ff:ee:12:00:03"


def test_one_vm_named_like_node():
    (vm,) = make(vcpus=2, memory=2048).vms()
    assert (vm.name, vm.node, vm.vcpus, vm.memory) == ("r3", "r3", 2, 2048)
    assert [(i.network, i.bridge, i.mac) for i in vm.interfaces] == [
        ("mgmt-1", None, "c0:ff:ee:03:00:01"),
        ("p2p-1", None, "c0:ff:ee:03:00:02"),
        (None, "br0", "c0:ff:ee:03:00:03"),
    ]
    assert make().vnets() == []


def test_port_needs_network_or_bridge():
    with pytest.raises(ValueError):
        Debian(name="x", id=1, user="u", ports=[Port()]).vms()


def test_meta_data_is_yaml():
    assert yaml.safe_load(make().meta_data()) == {"instance-id": "r3", "local-hostname": "r3"}


def test_user_data():
    text = make().user_data(["ssh-ed25519 AAAA key: with colon"])
    assert text.startswith("#cloud-config\n")
    user = yaml.safe_load(text)["users"][0]
    assert user["name"] == "omaxx"
    assert user["sudo"] == "ALL=(ALL) NOPASSWD:ALL"
    assert user["ssh_authorized_keys"] == ["ssh-ed25519 AAAA key: with colon"]


def test_network_config():
    eth = yaml.safe_load(make().network_config())["ethernets"]
    assert eth["port1"] == {
        "match": {"macaddress": "c0:ff:ee:03:00:01"},
        "addresses": ["172.255.1.3/24"],
        "routes": [{"to": "default", "via": "172.255.1.254"}],
        "nameservers": {"addresses": ["172.255.1.254"]},
    }
    assert eth["port2"] == {"match": {"macaddress": "c0:ff:ee:03:00:02"}, "addresses": ["192.168.1.3/24"]}
    assert eth["port3"] == {"match": {"macaddress": "c0:ff:ee:03:00:03"}}


def test_all_ssh_keys():
    host = FakeHost(files={"/k/a.pub": "key-a\n", "/k/auth": "# comment\nkey-b\n\nkey-c\n"})
    d = make(ssh_keys=["key-inline"], ssh_key_files=["/k/a.pub", "/k/auth"])
    assert d.all_ssh_keys(host) == ["key-inline", "key-a", "key-b", "key-c"]


NEW_FILES = [
    ("qemu-img", "create", "-f", "qcow2", "-F", "qcow2",
     "-b", "/var/lib/vlab/images/debian-13-genericcloud-amd64.qcow2", f"{VM_DIR}/r3.qcow2"),
    ("tee", f"{VM_DIR}/meta-data"),
    ("tee", f"{VM_DIR}/user-data"),
    ("tee", f"{VM_DIR}/network-config"),
    ("cloud-localds", "-N", f"{VM_DIR}/network-config", f"{VM_DIR}/seed.iso", f"{VM_DIR}/user-data", f"{VM_DIR}/meta-data"),
]


def test_prepare_new():
    host = FakeHost(files={"/k/a.pub": "key-a\n"})
    d = make(ssh_key_files=["/k/a.pub"])
    d.prepare(host, overwrite=False)
    assert host.commands() == [("test", "-e", VM_DIR), ("cat", "/k/a.pub"), ("mkdir", "-p", VM_DIR), *NEW_FILES]
    written = {cmd[1]: inp for cmd, inp in host.calls if cmd[0] == "tee"}
    assert yaml.safe_load(written[f"{VM_DIR}/user-data"])["users"][0]["ssh_authorized_keys"] == ["key-a"]
    assert written[f"{VM_DIR}/network-config"] == d.network_config()


def test_prepare_existing_kept():
    host = FakeHost(existing={VM_DIR})
    make().prepare(host, overwrite=False)
    assert host.commands() == [("test", "-e", VM_DIR)]


def test_prepare_existing_overwritten():
    host = FakeHost(existing={VM_DIR}, files={"/k/a.pub": "key-a\n"})
    make(ssh_key_files=["/k/a.pub"]).prepare(host, overwrite=True)
    assert host.commands() == [
        ("test", "-e", VM_DIR), ("cat", "/k/a.pub"), ("rm", "-r", VM_DIR), ("mkdir", "-p", VM_DIR), *NEW_FILES,
    ]


def test_from_dict():
    d = Debian.from_dict({"name": "r5", "id": 5, "user": "u", "ports": [{"network": "mgmt-1"}, {"bridge": "br0"}]})
    assert d.ports == [Port("mgmt-1"), Port(bridge="br0")]
    assert (d.vcpus, d.memory, d.image) == (1, 4096, "debian-13-genericcloud-amd64.qcow2")
    assert json.loads(d.meta_data())["instance-id"] == "r5"
