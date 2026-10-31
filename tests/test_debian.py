import json

import yaml

from vlab.spec import Debian, Port
from vlab.spec import debian as debian_mod

from conftest import FakeNode


def make(**kw) -> Debian:
    return Debian(
        id=3,
        user="omaxx",
        ports=[
            Port("mgmt-1", "172.255.1.3/24", gateway="172.255.1.254", dns=["172.255.1.254"]),
            Port("p2p-1", "192.168.1.3/24"),
            Port("p2p-2"),
        ],
        **kw,
    )


def test_name_and_mac():
    d = make()
    assert d.name == "vm-03"
    assert d.mac(1) == "c0:ff:ee:03:00:01"
    assert Debian(id=12, user="u").mac(3) == "c0:ff:ee:12:00:03"


def test_vm_spec():
    vm = make(vcpus=2, memory=2048).vm()
    assert (vm.name, vm.vcpus, vm.memory) == ("vm-03", 2, 2048)
    assert [(i.network, i.mac) for i in vm.interfaces] == [
        ("mgmt-1", "c0:ff:ee:03:00:01"),
        ("p2p-1", "c0:ff:ee:03:00:02"),
        ("p2p-2", "c0:ff:ee:03:00:03"),
    ]


def test_meta_data_is_yaml():
    assert yaml.safe_load(make().meta_data()) == {"instance-id": "vm-03", "local-hostname": "vm-03"}


def test_user_data():
    text = make().user_data(["ssh-ed25519 AAAA key: with colon"])
    assert text.startswith("#cloud-config\n")
    user = yaml.safe_load(text)["users"][0]
    assert user["name"] == "omaxx"
    assert user["sudo"] == "ALL=(ALL) NOPASSWD:ALL"
    assert user["ssh_authorized_keys"] == ["ssh-ed25519 AAAA key: with colon"]


def test_network_config():
    cfg = yaml.safe_load(make().network_config())
    assert cfg["version"] == 2
    eth = cfg["ethernets"]
    assert eth["port1"] == {
        "match": {"macaddress": "c0:ff:ee:03:00:01"},
        "addresses": ["172.255.1.3/24"],
        "routes": [{"to": "default", "via": "172.255.1.254"}],
        "nameservers": {"addresses": ["172.255.1.254"]},
    }
    assert eth["port2"] == {"match": {"macaddress": "c0:ff:ee:03:00:02"}, "addresses": ["192.168.1.3/24"]}
    assert eth["port3"] == {"match": {"macaddress": "c0:ff:ee:03:00:03"}}


def test_all_ssh_keys():
    node = FakeNode(files={"/k/a.pub": "key-a\n", "/k/auth": "# comment\nkey-b\n\nkey-c\n"})
    d = make(ssh_keys=["key-inline"], ssh_key_files=["/k/a.pub", "/k/auth"])
    assert d.all_ssh_keys(node) == ["key-inline", "key-a", "key-b", "key-c"]


def test_deploy(monkeypatch):
    defined = []
    monkeypatch.setattr(debian_mod, "define_vm", lambda node, vm: defined.append((node, vm)))
    node = FakeNode(files={"/k/a.pub": "key-a\n"})
    d = make(ssh_key_files=["/k/a.pub"])

    d.deploy(node)

    vm_dir = "/var/lib/vlab/vms/vm-03"
    assert node.commands() == [
        ("cat", "/k/a.pub"),
        ("mkdir", "-p", vm_dir),
        ("qemu-img", "create", "-f", "qcow2", "-F", "qcow2",
         "-b", "/var/lib/vlab/images/debian-13-genericcloud-amd64.qcow2", f"{vm_dir}/vm-03.qcow2"),
        ("tee", f"{vm_dir}/meta-data"),
        ("tee", f"{vm_dir}/user-data"),
        ("tee", f"{vm_dir}/network-config"),
        ("cloud-localds", "-N", f"{vm_dir}/network-config",
         f"{vm_dir}/seed.iso", f"{vm_dir}/user-data", f"{vm_dir}/meta-data"),
    ]
    written = {cmd[1]: inp for cmd, inp in node.calls if cmd[0] == "tee"}
    assert yaml.safe_load(written[f"{vm_dir}/user-data"])["users"][0]["ssh_authorized_keys"] == ["key-a"]
    assert written[f"{vm_dir}/network-config"] == d.network_config()
    assert defined == [(node, d.vm())]


def test_from_dict_defaults():
    d = Debian.from_dict({"id": 5, "user": "u", "ports": [{"network": "mgmt-1"}]})
    assert d.ports == [Port("mgmt-1")]
    assert (d.vcpus, d.memory, d.image) == (1, 4096, "debian-13-genericcloud-amd64.qcow2")
    assert json.loads(d.meta_data())["instance-id"] == "vm-05"
