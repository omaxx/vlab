from __future__ import annotations

from typing import Optional, Union, ClassVar, List, Self, Dict, Tuple
from enum import IntEnum

from dataclasses import dataclass, field, replace
import logging
from pathlib import Path
import json

from rich.tree import Tree
from rich.table import Table
import marshmallow
import marshmallow_dataclass
import yaml


FWD_MASK = "0xfff8"

logger = logging.getLogger(__name__)


class Schema(marshmallow.Schema):
    class Meta:
        unknown = marshmallow.EXCLUDE


@dataclass
class Image:
    path: str
    exist: Optional[bool] = None

    def __str__(self) -> str:
        return self.path


@dataclass
class Interface:
    bridge: Optional[str] = None
    network: Optional[str] = None

    mac: Optional[str] = None
    target: Optional[str] = None


@dataclass
class VM:
    class State(IntEnum):
        NOSTATE = 0
        RUNNING = 1
        BLOCKED = 2
        PAUSED = 3
        SHUTDOWN = 4
        SHUTOFF = 5
        CRASHED = 6
        PMSUSPENDED = 7
        ABSEND = -1

    name: str
    xml: str
    vcpu: int
    memory: int
    path: str
    src: str
    images: List[Image]
    interfaces: List[Interface]
    console: Optional[int] = None

    state: VM.State = State.NOSTATE

    def __rich__(self) -> Tree:
        table = Table.grid(expand=True)
        table.add_column()
        table.add_column(justify="right")
        table.add_row(self.name, self.state.name, style="bold")
        tree = Tree(table)
        for image in self.images[0:1]:
            table = Table.grid(expand=True)
            table.add_column()
            table.add_column(justify="right")
            table.add_row(image.path, str(image.exist))
            tree.add(table)
        return tree


@dataclass
class VNet:
    name: str
    xml: str = "network"

    state: Optional[int] = None

    def __eq__(self, other) -> bool:
        return isinstance(other, VNet) and other.name == self.name

    def __rich__(self) -> Table:
        table = Table.grid(expand=True)
        table.add_column()
        table.add_column(justify="right")
        table.add_row(self.name, str(self.state), style="italic")
        return table


@dataclass
class Device:
    name: str
    interfaces: List[Interface] = field(default_factory=list)

    vms: List[VM] = field(default_factory=list)
    vnets: List[VNet] = field(default_factory=list)

    vmx: Optional[VMX] = None

    def __post_init__(self):
        if self.vmx is not None:
            self.vmx.load(self)

    def __rich__(self) -> Tree:
        tree = Tree(self.name)
        for vm in self.vms:
            tree.add(vm)
        for vnet in self.vnets:
            tree.add(vnet)
        return tree


@dataclass
class Topology:
    name: str = "vlab"
    devices: List[Device] = field(default_factory=list)
    vnets: List[VNet] = field(default_factory=list)

    def __post_init__(self):
        for device in self.devices:
            for interface in device.interfaces:
                if (vnet := VNet(interface.network)) not in self.vnets:
                    self.vnets.append(vnet)

    @classmethod
    def load(cls, file: Union[str, Path]) -> Self:
        if not isinstance(file, Path):
            file = Path(file)
        name = file.with_suffix("").name
        schema = marshmallow_dataclass.class_schema(Topology, base_schema=Schema)()
        with open(file) as io:
            if file.suffix == ".json":
                return schema.load({"name": name, **json.load(io)})
            if file.suffix in [".yaml", ".yml"]:
                return schema.load({"name": name, **(yaml.safe_load(io) or {})})
            logger.critical(f"Unknown topology file format: `{file.suffix}`")


RE_CONSOLE_PORT = 8600
FPC_CONSOLE_PORT = 9600


@dataclass
class VMX:
    id: int
    images: str
    re_image: str
    fpc_image: str

    re_num: int = 1
    re_vcpu: int = 1
    re_memory: int = 1024
    fpc_num: int = 1
    fpc_vcpu: int = 3
    fpc_memory: int = 2048

    def load(self, device: Device):
        device.vms = [
            VM(
                name=f"{device.name}~re{slot}",
                xml="jnpr-vmx-re",
                path=f"{device.name}/re{slot}",
                vcpu=self.re_vcpu,
                memory=self.re_memory,
                src=self.images,
                images=[
                    Image(path=self.re_image),
                    Image(path="vmxhdd.img"),
                    Image(path=f"metadata-usb-re{slot}.img"),
                ],
                interfaces=[
                    Interface(
                        bridge="mgmt",
                        target=f"{device.name}~re{slot}~mgmt",
                        mac=f"C0:FF:EE:{self.id}:{10 + slot}:00",
                    ),
                    Interface(
                        network=f"{device.name}~int",
                        target=f"{device.name}~re{slot}~int",
                    ),
                ],
                console=RE_CONSOLE_PORT+self.id+100*slot,
            ) for slot in range(self.re_num)
        ] + [
            VM(
                name=f"{device.name}~fpc{slot}",
                xml="jnpr-vmx-fpc",
                path=f"{device.name}/fpc{slot}",
                vcpu=self.fpc_vcpu,
                memory=self.fpc_memory,
                src=self.images,
                images=[
                    Image(path=self.fpc_image),
                    Image(path=f"metadata-usb-fpc{slot}.img"),
                ],
                interfaces=[
                    Interface(
                        bridge="mgmt",
                        target=f"{device.name}~fpc{slot}~mgmt",
                        mac=f"C0:FF:EE:{self.id}:{slot}:ff",
                    ),
                    Interface(
                        network=f"{device.name}~int",
                        target=f"{device.name}~fpc{slot}~int",
                    ),
                ] + [
                    replace(
                        interface,
                        target=f"{device.name}~fpc{slot}~{num}",
                        mac=f"C0:FF:EE:{self.id}:{slot}:{num}",
                    )
                    for num, interface in enumerate(device.interfaces)
                ],
                console=FPC_CONSOLE_PORT + self.id + 100 * slot,
            ) for slot in range(self.fpc_num)

        ]
        device.vnets = [
            VNet(name=f"{device.name}~int"),
        ]
