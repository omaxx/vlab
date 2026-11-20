from dataclasses import dataclass, field
import json
import logging
from typing import Any, ClassVar

from ..host import Host
from ..virt import VM, DHCPHost, Disk
from .device import Device
from .port import Port

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class Linux(Device):
    """Linux cloud image device (Debian, Ubuntu, ... with cloud-init): one VM named like the device,
    qcow2 overlay on base image + cloud-init seed.

    Port N (1-based): MAC ca:ff:ee:<id>:00:<N> (id as 2 decimal digits, locally administered),
    host interface <device>-<N>.
    cloud-init installs and starts qemu-guest-agent (needs package mirror access, e.g. via NAT mgmt network).
    """

    type: ClassVar[str] = "linux"
    id: int  # 1-99
    user: str  # $VAR allowed, e.g. $USER: taken from host env at deploy
    ssh_keys: list[str] = field(default_factory=list)
    ssh_key_files: list[str] = field(default_factory=list)  # paths on host (~ allowed), one key per line
    ports: list[Port] = field(default_factory=list)
    vcpus: int = 1
    memory: int = 4096  # MiB
    image: str = "debian-13-genericcloud-amd64.qcow2"  # in images_dir(host): <host.images_dir>/linux

    def mac(self, n: int) -> str:
        return f"ca:ff:ee:{self.id:02d}:00:{n:02d}"

    def dhcp_leases(self) -> list[tuple[str, DHCPHost]]:
        leases = []
        for n, p in enumerate(self.ports, 1):
            if not p.dhcp:
                continue
            if p.network is None or p.ip is None:
                raise ValueError(f"{self.name}: port {n}: dhcp needs network and ip")
            leases.append((p.network, DHCPHost(self.mac(n), p.ip.split("/")[0], self.name)))
        return leases

    def vms(self) -> list[VM]:
        return [
            VM(
                name=self.name,
                device=self.name,
                vcpus=self.vcpus,
                memory=self.memory,
                disks=[
                    Disk(f"{self.name}.qcow2", "vda"),
                    Disk("seed.iso", "sda", format="raw", bus="sata", device="cdrom"),
                ],
                interfaces=[p.interface(self.mac(n), f"{self.name}-{n}") for n, p in enumerate(self.ports, 1)],
            )
        ]

    # cloud-init files: JSON is valid YAML, so no YAML library or manual quoting needed

    def meta_data(self) -> str:
        return json.dumps({"instance-id": self.name, "local-hostname": self.name}, indent=2) + "\n"

    def user_data(self, user: str, ssh_keys: list[str]) -> str:
        cfg = {
            "users": [
                {
                    "name": user,
                    "shell": "/bin/bash",
                    "sudo": "ALL=(ALL) NOPASSWD:ALL",
                    "ssh_authorized_keys": ssh_keys,
                }
            ],
            "packages": ["qemu-guest-agent"],
            # agent unit is started by udev on the virtio port, which appeared before the package was installed
            "runcmd": [["systemctl", "start", "qemu-guest-agent"]],
        }
        return "#cloud-config\n" + json.dumps(cfg, indent=2) + "\n"

    def network_config(self) -> str:
        ethernets: dict[str, dict[str, Any]] = {}
        for n, p in enumerate(self.ports, 1):
            eth: dict[str, Any] = {"match": {"macaddress": self.mac(n)}}
            if p.ip:
                eth["addresses"] = [p.ip]
            if p.gateway:
                eth["routes"] = [{"to": "default", "via": p.gateway}]
            if p.dns:
                eth["nameservers"] = {"addresses": p.dns}
            ethernets[f"port{n}"] = eth
        return json.dumps({"version": 2, "ethernets": ethernets}, indent=2) + "\n"

    def all_ssh_keys(self, host: Host) -> list[str]:
        keys = list(self.ssh_keys)
        for f in self.ssh_key_files:
            keys += [k for k in host.read(f).splitlines() if k.strip() and not k.startswith("#")]
        return keys

    def prepare(self, host: Host, overwrite: bool) -> None:
        d = host.vm_dir(self.name)
        exists = host.exists(d)
        if exists and not overwrite:
            logger.info("%s: VM `%s`: files kept", host, self.name)
            return
        user = host.expand_vars(self.user)  # resolve first: fail before changing anything
        ssh_keys = self.all_ssh_keys(host)
        if exists:
            host.rm(d)
        host.mkdir(d)
        host.cow(f"{self.images_dir(host)}/{self.image}", f"{d}/{self.name}.qcow2")
        host.write(f"{d}/meta-data", self.meta_data())
        host.write(f"{d}/user-data", self.user_data(user, ssh_keys))
        host.write(f"{d}/network-config", self.network_config())
        host.seed_iso(f"{d}/seed.iso", f"{d}/user-data", f"{d}/meta-data", f"{d}/network-config")
        logger.info("%s: VM `%s`: files %s", host, self.name, "rewritten" if exists else "created")
