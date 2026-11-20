"""libvirt operations on a host. All libvirt calls of vlab live in this module.

VNet rules: only networks with vlab metadata (VNet.managed) are started/stopped; others are never touched.
A managed network is stopped when no running VM is attached to it.
Device networks (meta devices list) are created by attach_vnet and undefined by delete_vms when their
last device is gone.
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
import logging
import time
import xml.etree.ElementTree as ET

import libvirt

from ..host import Host
from .vm import VM
from .meta import NS
from .vnet import DHCPHost, VNet

logger = logging.getLogger(__name__)

SHUTDOWN_FLAGS = libvirt.VIR_DOMAIN_SHUTDOWN_GUEST_AGENT | libvirt.VIR_DOMAIN_SHUTDOWN_ACPI_POWER_BTN
POLL = 0.5  # seconds between checks while waiting for clean shutdown


@contextmanager
def _connect(host: Host) -> Iterator[libvirt.virConnect]:
    conn = libvirt.open(host.libvirt_uri)
    try:
        yield conn
    finally:
        conn.close()


def define_vm(host: Host, vm: VM) -> None:
    """Define (create persistent, not start) VM on host from its XML."""
    xml = vm.to_xml(host)
    logger.debug("%s: VM `%s` XML:\n%s", host, vm.name, xml)
    with _connect(host) as conn:
        conn.defineXML(xml)
    logger.info("%s: VM `%s`: DEFINED", host, vm.name)


def define_vnet(host: Host, vnet: VNet) -> None:
    """Define (create persistent, not start, no autostart) network on host from its XML."""
    xml = vnet.to_xml()
    logger.debug("%s: VNet `%s` XML:\n%s", host, vnet.name, xml)
    with _connect(host) as conn:
        conn.networkDefineXML(xml)
    logger.info("%s: VNet `%s`: DEFINED", host, vnet.name)


def list_vms(host: Host) -> list[tuple[VM, bool]]:
    """All VMs on host with active flag, sorted by name."""
    with _connect(host) as conn:
        doms = sorted(conn.listAllDomains(), key=lambda d: d.name())
        return [(VM.from_xml(d.XMLDesc()), bool(d.isActive())) for d in doms]


def list_vnets(host: Host) -> list[tuple[VNet, bool]]:
    """All networks on host with active flag, sorted by name."""
    with _connect(host) as conn:
        nets = sorted(conn.listAllNetworks(), key=lambda n: n.name())
        return [(VNet.from_xml(n.XMLDesc()), bool(n.isActive())) for n in nets]


def start_vms(host: Host, *names: str) -> None:
    """Start VMs; their managed networks are started first."""
    with _connect(host) as conn:
        for name in names:
            dom = conn.lookupByName(name)
            _start_vnets(conn, host, VM.from_xml(dom.XMLDesc()).networks())
            if not dom.isActive():
                dom.create()
                logger.info("%s: VM `%s`: STARTED", host, name)


def stop_vms(host: Host, *names: str, force: bool = False, timeout: float = 60) -> None:
    """Stop VMs, then their managed networks that are no longer used.

    Clean shutdown (guest agent or ACPI power button) for all VMs at once, wait up to timeout seconds,
    then force off what still runs. force=True: force off right away.
    """
    with _connect(host) as conn:
        doms = [conn.lookupByName(name) for name in names]
        running = [d for d in doms if d.isActive()]
        if not force and running:
            for dom in running:
                _shutdown(host, dom)
            deadline = time.monotonic() + timeout
            while any(d.isActive() for d in running) and time.monotonic() < deadline:
                time.sleep(POLL)
        for dom in running:
            if dom.isActive():
                dom.destroy()
                logger.info("%s: VM `%s`: STOPPED%s", host, dom.name(), "" if force else " (forced after timeout)")
            else:
                logger.info("%s: VM `%s`: STOPPED", host, dom.name())
        for dom in doms:
            _stop_vnets(conn, host, VM.from_xml(dom.XMLDesc()).networks())


def delete_vms(host: Host, *names: str) -> None:
    """Force off and undefine VMs (incl. UEFI NVRAM), stop their unused managed networks, then release
    device networks: a device no longer having any VM on one is removed from its devices; network
    undefined when none is left. Files stay."""
    with _connect(host) as conn:
        used: set[tuple[str, str]] = set()  # (network, device) of deleted VMs
        for name in names:
            dom = conn.lookupByName(name)
            xml = dom.XMLDesc()
            vm = VM.from_xml(xml)
            networks = vm.networks()
            if vm.device is not None:
                used |= {(n, vm.device) for n in networks}
            if dom.isActive():
                dom.destroy()
                logger.info("%s: VM `%s`: STOPPED", host, name)
            has_nvram = ET.fromstring(xml).find("os/nvram") is not None  # UEFI vars file
            dom.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_NVRAM if has_nvram else 0)
            logger.info("%s: VM `%s`: DELETED", host, name)
            for iface in vm.interfaces:
                if iface.type == "network" and iface.mac:
                    _remove_dhcp_host(conn, host, iface.source, iface.mac)
            _stop_vnets(conn, host, networks)
        remaining = {(n, v.device) for v in (VM.from_xml(d.XMLDesc()) for d in conn.listAllDomains()) for n in v.networks()}
        for network, device in sorted(used - remaining):
            _release_vnet(conn, host, network, device)


def attach_vnet(host: Host, template: VNet, device: str) -> None:
    """Device network for device: create from template (devices=[device]) if missing, else add device
    to its devices. Existing networks without meta devices (regular, outside vlab) are used as they are."""
    with _connect(host) as conn:
        try:
            net = conn.networkLookupByName(template.name)
        except libvirt.libvirtError:
            vnet = VNet(template.name, template.bridge, template.ip, template.forward, devices=[device],
                        mtu=template.mtu, dhcp=template.dhcp)
            conn.networkDefineXML(vnet.to_xml())
            logger.info("%s: VNet `%s`: DEFINED for %s", host, vnet.name, device)
            return
        current = VNet.from_xml(net.XMLDesc())
        if current.devices is None:
            logger.debug("%s: VNet `%s`: no meta devices, used as is by %s", host, current.name, device)
        elif device not in current.devices:
            _set_devices(net, [*current.devices, device])
            logger.info("%s: VNet `%s`: %s attached (devices: %s)", host, current.name, device,
                        ", ".join([*current.devices, device]))


def _release_vnet(conn: libvirt.virConnect, host: Host, network: str, device: str) -> None:
    try:
        net = conn.networkLookupByName(network)
    except libvirt.libvirtError:
        return
    vnet = VNet.from_xml(net.XMLDesc())
    if vnet.devices is None or device not in vnet.devices:
        return
    devices = [d for d in vnet.devices if d != device]
    if devices:
        _set_devices(net, devices)
        logger.info("%s: VNet `%s`: %s detached (devices: %s)", host, network, device, ", ".join(devices))
        return
    if net.isActive():
        net.destroy()
    net.undefine()
    logger.info("%s: VNet `%s`: DELETED (last device %s gone)", host, network, device)


def _set_devices(net: libvirt.virNetwork, devices: list[str]) -> None:
    """Replace the network's vlab metadata in place (no redefine/restart)."""
    meta = ET.Element("network")  # libvirt puts it into the vlab namespace (key + NS)
    elem = ET.SubElement(meta, "devices")
    for d in devices:
        ET.SubElement(elem, "device").text = d
    flags = libvirt.VIR_NETWORK_UPDATE_AFFECT_CONFIG
    if net.isActive():
        flags |= libvirt.VIR_NETWORK_UPDATE_AFFECT_LIVE
    net.setMetadata(libvirt.VIR_NETWORK_METADATA_ELEMENT, ET.tostring(meta, encoding="unicode"), "vlab", NS, flags)


def set_dhcp_host(host: Host, network: str, lease: DHCPHost) -> None:
    """Add or replace (same MAC) a fixed DHCP lease in a managed network, live if running (no restart).

    A named lease also gets a DNS host entry: dnsmasq serves names of DHCP hosts added to a running
    network only after restart, DNS host entries right away.
    Networks without vlab metadata are not touched (warning).
    """
    with _connect(host) as conn:
        net = conn.networkLookupByName(network)
        vnet = VNet.from_xml(net.XMLDesc())
        if not vnet.managed:
            logger.warning("%s: VNet `%s`: not managed by vlab, DHCP host %s not added", host, network, lease.mac)
            return
        current = vnet.dhcp.hosts if vnet.dhcp else []
        same = [h for h in current if h.mac == lease.mac]
        if same == [lease]:
            logger.debug("%s: VNet `%s`: DHCP host %s unchanged", host, network, lease.mac)
        else:
            for old in same:
                _update(net, libvirt.VIR_NETWORK_UPDATE_COMMAND_DELETE, DHCP_HOST, _xml(old.to_xml()))
                _remove_dns_host(net, old)
            _update(net, libvirt.VIR_NETWORK_UPDATE_COMMAND_ADD_LAST, DHCP_HOST, _xml(lease.to_xml()))
            logger.info("%s: VNet `%s`: DHCP host %s -> %s (%s)", host, network, lease.mac, lease.ip, lease.name)
        if lease.name and (lease.ip, lease.name) not in _dns_hosts(net):
            _update(net, libvirt.VIR_NETWORK_UPDATE_COMMAND_ADD_LAST, DNS_HOST, _dns_host_xml(lease))


def remove_dhcp_host(host: Host, network: str, mac: str) -> None:
    """Remove fixed DHCP lease of MAC (and its DNS host entry) from a managed network, if present."""
    with _connect(host) as conn:
        _remove_dhcp_host(conn, host, network, mac)


DHCP_HOST = libvirt.VIR_NETWORK_SECTION_IP_DHCP_HOST
DNS_HOST = libvirt.VIR_NETWORK_SECTION_DNS_HOST


def _remove_dhcp_host(conn: libvirt.virConnect, host: Host, network: str, mac: str) -> None:
    try:
        net = conn.networkLookupByName(network)
    except libvirt.libvirtError:
        return  # network gone: nothing to clean up
    vnet = VNet.from_xml(net.XMLDesc())
    if not vnet.managed or vnet.dhcp is None:
        return
    for lease in [h for h in vnet.dhcp.hosts if h.mac == mac]:
        _update(net, libvirt.VIR_NETWORK_UPDATE_COMMAND_DELETE, DHCP_HOST, _xml(lease.to_xml()))
        _remove_dns_host(net, lease)
        logger.info("%s: VNet `%s`: DHCP host %s removed", host, network, mac)


def _dns_hosts(net: libvirt.virNetwork) -> set[tuple[str, str]]:
    """(ip, hostname) pairs of the network's DNS host entries."""
    root = ET.fromstring(net.XMLDesc())
    return {(h.get("ip", ""), n.text or "") for h in root.iterfind("dns/host") for n in h.iterfind("hostname")}


def _dns_host_xml(lease: DHCPHost) -> str:
    entry = ET.Element("host", ip=lease.ip)
    ET.SubElement(entry, "hostname").text = lease.name
    return _xml(entry)


def _remove_dns_host(net: libvirt.virNetwork, lease: DHCPHost) -> None:
    if lease.name and (lease.ip, lease.name) in _dns_hosts(net):
        _update(net, libvirt.VIR_NETWORK_UPDATE_COMMAND_DELETE, DNS_HOST, _dns_host_xml(lease))


def _xml(elem: ET.Element) -> str:
    return ET.tostring(elem, encoding="unicode")


def _update(net: libvirt.virNetwork, command: int, section: int, xml: str) -> None:
    flags = libvirt.VIR_NETWORK_UPDATE_AFFECT_CONFIG
    if net.isActive():
        flags |= libvirt.VIR_NETWORK_UPDATE_AFFECT_LIVE
    net.update(command, section, -1, xml, flags)


def start_vnets(host: Host, *names: str) -> None:
    with _connect(host) as conn:
        _start_vnets(conn, host, names)


def stop_vnets(host: Host, *names: str) -> None:
    """Stop managed networks that no running VM uses."""
    with _connect(host) as conn:
        _stop_vnets(conn, host, names)


def _shutdown(host: Host, dom: libvirt.virDomain) -> None:
    """Ask guest to shut down: guest agent or ACPI; plain shutdown() if the driver rejects these flags."""
    try:
        dom.shutdownFlags(SHUTDOWN_FLAGS)
        return
    except libvirt.libvirtError as e:
        logger.debug("%s: VM `%s`: shutdown via agent/ACPI failed: %s", host, dom.name(), e)
    try:
        dom.shutdown()
    except libvirt.libvirtError as e:
        logger.debug("%s: VM `%s`: shutdown failed: %s", host, dom.name(), e)


def _start_vnets(conn: libvirt.virConnect, host: Host, names: Iterable[str]) -> None:
    for name in dict.fromkeys(names):  # dedupe, keep order
        net = conn.networkLookupByName(name)
        if not VNet.from_xml(net.XMLDesc()).managed:
            logger.debug("%s: VNet `%s`: not managed by vlab, skipped", host, name)
        elif not net.isActive():
            net.create()
            logger.info("%s: VNet `%s`: STARTED", host, name)


def _stop_vnets(conn: libvirt.virConnect, host: Host, names: Iterable[str]) -> None:
    for name in dict.fromkeys(names):
        net = conn.networkLookupByName(name)
        if not VNet.from_xml(net.XMLDesc()).managed:
            logger.debug("%s: VNet `%s`: not managed by vlab, skipped", host, name)
        elif net.isActive():
            if users := _active_vms_on(conn, name):
                logger.debug("%s: VNet `%s`: in use by %s, kept", host, name, ", ".join(users))
            else:
                net.destroy()
                logger.info("%s: VNet `%s`: STOPPED", host, name)


def _active_vms_on(conn: libvirt.virConnect, network: str) -> list[str]:
    doms = conn.listAllDomains(libvirt.VIR_CONNECT_LIST_DOMAINS_ACTIVE)
    return [d.name() for d in doms if network in VM.from_xml(d.XMLDesc()).networks()]
