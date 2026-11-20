from dataclasses import dataclass, field
from typing import cast

from ..virt import Interface
from ..virt.vm import NicModel, NicType


@dataclass
class Port:
    """NIC: exactly one of
      network: existing libvirt network (not checked)
      bridge: existing host bridge (not checked)
      p2p: stub link network - created on deploy if missing, shared via meta devices, removed with last device
      udp: tunnel to remote "addr:port" (+ local)

    ip/gateway/routes/dns: guest config, used by device types that configure the guest (e.g. Linux via cloud-init).
    dhcp: fixed DHCP lease for ip (+ DNS name) in the network, registered on deploy.
    """

    network: str | None = None
    ip: str | None = None  # with prefix, e.g. "172.255.1.1/24"
    gateway: str | None = None
    routes: dict[str, str] = field(default_factory=dict)  # static routes: prefix -> next hop
    dns: list[str] = field(default_factory=list)
    bridge: str | None = None
    p2p: str | None = None
    udp: str | None = None  # remote "addr:port"
    local: str | None = None  # own "addr:port" for udp
    target: str | None = None  # host-side interface name (network/bridge); default "<device>-<N>" if <= 15 chars
    model: NicModel = "virtio"
    dhcp: bool = False  # register fixed DHCP lease (ip, device name for DNS) in network on deploy

    def interface(self, mac: str, default_target: str) -> Interface:
        sources = {"network": self.network, "bridge": self.bridge, "p2p": self.p2p, "udp": self.udp}
        given = [(t, s) for t, s in sources.items() if s is not None]
        if len(given) != 1:
            raise ValueError("Port needs exactly one of network, bridge, p2p or udp")
        type_, source = given[0]
        if type_ == "p2p":  # a libvirt network on the VM side
            type_ = "network"
        target = self.target
        if target is None and type_ != "udp" and len(default_target) <= 15:  # Linux ifname limit
            target = default_target
        return Interface(cast(NicType, type_), source, target=target, local=self.local, mac=mac, model=self.model)
