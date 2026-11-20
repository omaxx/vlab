from collections.abc import Hashable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..host import Host
from ..utils import load_file
from .device import Device
from .network import Network


@dataclass
class Topology:
    """Lab topology file: `devices:` and `networks:` maps of name -> spec (name may be omitted in the spec).
    Top-level keys starting with `x-` are ignored: a place for YAML anchors (`x-vmx: &vmx` ... `<<: *vmx`).

    Spec-relative files (e.g. configs/ templates) resolve against the topology file's folder.
    """

    devices: list[Device] = field(default_factory=list)
    networks: list[Network] = field(default_factory=list)

    def deploy(self, host: Host, overwrite: bool = False) -> None:
        """Networks first, then devices."""
        for network in self.networks:
            network.deploy(host)
        for device in self.devices:
            device.deploy(host, overwrite=overwrite)


def load_topology(path: str) -> Topology:
    data = load_file(path)
    unknown = {k for k in data if not str(k).startswith("x-")} - {"devices", "networks"}
    if unknown:
        raise ValueError(
            f"{path}: unknown top-level keys {sorted(map(str, unknown))}, expected devices, networks, x-*"
        )
    spec_dir = str(Path(path).resolve().parent)
    devices = []
    for name, spec in _named(path, data.get("devices"), "devices"):
        device = Device.from_dict(spec)
        device.resolve(spec_dir)
        devices.append(device)
    networks = [Network.from_dict(spec) for _, spec in _named(path, data.get("networks"), "networks")]
    return Topology(devices=devices, networks=networks)


def _named(path: str, section: Any, key: str) -> list[tuple[str, dict[Hashable, Any]]]:
    """Section map name -> spec: copy each spec with name filled in; name in spec must match the key."""
    if section is None:
        return []
    if not isinstance(section, dict):
        raise ValueError(f"{path}: {key} must be a map of name -> spec")
    res = []
    for name, spec in section.items():
        spec = dict(spec or {})
        if spec.setdefault("name", name) != name:
            raise ValueError(f"{path}: {key}.{name}: name {spec['name']!r} differs from key")
        res.append((str(name), spec))
    return res

