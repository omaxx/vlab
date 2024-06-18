from __future__ import annotations
from typing import List, Optional
from dataclasses import dataclass, field, InitVar
import marshmallow_dataclass


@dataclass
class VM:
    name: str


@dataclass
class Device:
    name: str

    vms: List[VM] = field(init=False)

    vmx: Optional[VMX] = field(repr=False, default=None)

    def __post_init__(self):
        if self.vmx is not None:
            self.vmx.load(self)


@dataclass
class VMX:
    vre: int = 1
    vfpc: int = 1

    def load(self, device: Device):
        device.vms = [VM(name=f"re{i}") for i in range(self.vre)]


device = marshmallow_dataclass.class_schema(Device)().load({"name": "first", "vmx": {"vre": 2}})
print(device)