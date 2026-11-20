"""libvirt operations on a host. All libvirt calls of vlab live in this module.

VNet rule: only networks with vlab metadata (VNet.managed) are started/stopped; others are never touched.
A managed network is stopped when no running VM is attached to it.
"""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
import logging
import time
import xml.etree.ElementTree as ET

import libvirt

from ..host import Host
from .vm import VM
from .vnet import VNet

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
    """Force off and undefine VMs (incl. UEFI NVRAM), then stop their unused managed networks. Files stay."""
    with _connect(host) as conn:
        for name in names:
            dom = conn.lookupByName(name)
            xml = dom.XMLDesc()
            networks = VM.from_xml(xml).networks()
            if dom.isActive():
                dom.destroy()
                logger.info("%s: VM `%s`: STOPPED", host, name)
            has_nvram = ET.fromstring(xml).find("os/nvram") is not None  # UEFI vars file
            dom.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_NVRAM if has_nvram else 0)
            logger.info("%s: VM `%s`: DELETED", host, name)
            _stop_vnets(conn, host, networks)


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
