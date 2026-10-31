from dataclasses import dataclass, field
import json

from mashumaro import DataClassDictMixin

from ..node import Node
from ..virt import VM, Interface, define_vm


@dataclass
class Port:
    network: str  # libvirt network name
    ip: str | None = None  # with prefix, e.g. "172.255.1.1/24"
    gateway: str | None = None
    dns: list[str] = field(default_factory=list)


@dataclass
class Debian(DataClassDictMixin):
    """Debian cloud image VM: qcow2 overlay on base image + cloud-init seed, defined on libvirt (not started).

    MAC of port N (1-based): c0:ff:ee:<id>:00:<N>, id as 2 decimal digits.
    """

    id: int  # 1-99
    user: str
    ssh_keys: list[str] = field(default_factory=list)
    ssh_key_files: list[str] = field(default_factory=list)  # absolute paths on node, one key per line
    ports: list[Port] = field(default_factory=list)
    vcpus: int = 1
    memory: int = 4096  # MiB
    image: str = "debian-13-genericcloud-amd64.qcow2"  # in node.images_dir

    @property
    def name(self) -> str:
        return f"vm-{self.id:02d}"

    def mac(self, n: int) -> str:
        return f"c0:ff:ee:{self.id:02d}:00:{n:02d}"

    def vm(self) -> VM:
        return VM(
            name=self.name,
            vcpus=self.vcpus,
            memory=self.memory,
            interfaces=[Interface(p.network, self.mac(n)) for n, p in enumerate(self.ports, 1)],
        )

    # cloud-init files: JSON is valid YAML, so no YAML library or manual quoting needed

    def meta_data(self) -> str:
        return json.dumps({"instance-id": self.name, "local-hostname": self.name}, indent=2) + "\n"

    def user_data(self, ssh_keys: list[str]) -> str:
        cfg = {
            "users": [
                {
                    "name": self.user,
                    "shell": "/bin/bash",
                    "sudo": "ALL=(ALL) NOPASSWD:ALL",
                    "ssh_authorized_keys": ssh_keys,
                }
            ]
        }
        return "#cloud-config\n" + json.dumps(cfg, indent=2) + "\n"

    def network_config(self) -> str:
        ethernets = {}
        for n, p in enumerate(self.ports, 1):
            eth: dict = {"match": {"macaddress": self.mac(n)}}
            if p.ip:
                eth["addresses"] = [p.ip]
            if p.gateway:
                eth["routes"] = [{"to": "default", "via": p.gateway}]
            if p.dns:
                eth["nameservers"] = {"addresses": p.dns}
            ethernets[f"port{n}"] = eth
        return json.dumps({"version": 2, "ethernets": ethernets}, indent=2) + "\n"

    def all_ssh_keys(self, node: Node) -> list[str]:
        keys = list(self.ssh_keys)
        for f in self.ssh_key_files:
            keys += [k for k in node.read(f).splitlines() if k.strip() and not k.startswith("#")]
        return keys

    def deploy(self, node: Node) -> None:
        ssh_keys = self.all_ssh_keys(node)  # read first: fail before changing anything
        d = node.vm_dir(self.name)
        node.mkdir(d)
        node.cow(f"{node.images_dir}/{self.image}", f"{d}/{self.name}.qcow2")
        node.write(f"{d}/meta-data", self.meta_data())
        node.write(f"{d}/user-data", self.user_data(ssh_keys))
        node.write(f"{d}/network-config", self.network_config())
        node.seed_iso(f"{d}/seed.iso", f"{d}/user-data", f"{d}/meta-data", f"{d}/network-config")
        define_vm(node, self.vm())
