from dataclasses import dataclass, field
import logging
from typing import Literal

from mashumaro import DataClassDictMixin

from ..host import Host
from ..virt import VNet, define_vnet, list_vnets

logger = logging.getLogger(__name__)


@dataclass
class Network(DataClassDictMixin):
    """Lab network shared by devices (e.g. mgmt): one libvirt VNet, always with vlab metadata (managed)."""

    name: str
    bridge: str | None = None  # default: same as name
    ip: str | None = None  # host IP with prefix, e.g. "172.255.1.254/24"
    forward: Literal["nat", "route", "open"] | None = None  # None = isolated
    devices: list[str] = field(default_factory=list)  # owning devices, empty = shared

    def vnets(self) -> list[VNet]:
        return [VNet(self.name, self.bridge, self.ip, self.forward, devices=list(self.devices))]

    def deploy(self, host: Host) -> None:
        """Define VNet on host (not started); an existing one with the same name is kept."""
        define_missing_vnets(host, self.vnets())


def define_missing_vnets(host: Host, vnets: list[VNet]) -> None:
    existing = {vnet.name for vnet, _ in list_vnets(host)}
    for vnet in vnets:
        if vnet.name in existing:
            logger.info("%s: VNet `%s`: exists, kept", host, vnet.name)
        else:
            define_vnet(host, vnet)
