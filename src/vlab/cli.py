from collections.abc import Callable
import logging
from typing import Any, TypeVar

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from . import spec, virt
from .host import Host
from .spec import Debian, Network
from .utils import load_file

LOG_LEVELS = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}

F = TypeVar("F", bound=Callable[..., Any])


@click.group()
@click.option("-v", "--verbose", count=True, help="-v: info, -vv: debug")
@click.pass_context
def main(ctx: click.Context, verbose: int) -> None:
    """Virtual lab on libvirt."""
    logging.basicConfig(
        level=LOG_LEVELS[min(verbose, 2)], format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
    )
    ctx.obj = Host()


SPEC_FILE = click.Path(exists=True, dir_okay=False)


@main.command()
@click.option("-d", "--device", "devices", multiple=True, type=SPEC_FILE, help="device spec file (repeatable)")
@click.option("-n", "--network", "networks", multiple=True, type=SPEC_FILE, help="network spec file (repeatable)")
@click.option("--overwrite", is_flag=True, help="rewrite existing VM files instead of keeping them")
@click.pass_obj
def deploy(host: Host, devices: tuple[str, ...], networks: tuple[str, ...], overwrite: bool) -> None:
    """Define networks, then devices (VNets + VMs) on host, not started. Spec: .yaml, .json or .jsonnet."""
    if not (devices or networks):
        raise click.UsageError("give -d DEVICE_FILE and/or -n NETWORK_FILE")
    for path in networks:
        network = Network.from_dict(load_file(path))
        network.deploy(host)
        click.echo(f"network {network.name} deployed")
    for path in devices:
        device = Debian.from_dict(load_file(path))
        device.deploy(host, overwrite=overwrite)
        click.echo(f"device {device.name} deployed")


def select_vms(host: Host, vms: tuple[str, ...], devices: tuple[str, ...], all_: bool) -> list[str]:
    """VM names: given VM names + VMs of given devices; --all = every VM with vlab metadata."""
    if not (vms or devices or all_):
        raise click.UsageError("give VM names, --device or --all")
    selected = list(vms)
    for vm, _ in virt.list_vms(host):
        if vm.device is not None and (all_ or vm.device in devices) and vm.name not in selected:
            selected.append(vm.name)
    return selected


def vm_selection(f: F) -> F:
    """Add VM selection: VMS arguments, -d DEVICE, --all."""
    f = click.argument("vms", nargs=-1)(f)
    f = click.option("-d", "--device", "devices", multiple=True, help="all VMs of device (repeatable)")(f)
    f = click.option("--all", "all_", is_flag=True, help="all VMs managed by vlab")(f)
    return f


@main.command()
@vm_selection
@click.pass_obj
def start(host: Host, vms: tuple[str, ...], devices: tuple[str, ...], all_: bool) -> None:
    """Start VMs and their vlab VNets."""
    virt.start_vms(host, *select_vms(host, vms, devices, all_))


@main.command()
@vm_selection
@click.pass_obj
def stop(host: Host, vms: tuple[str, ...], devices: tuple[str, ...], all_: bool) -> None:
    """Force off VMs, stop vlab VNets no longer used."""
    virt.stop_vms(host, *select_vms(host, vms, devices, all_))


@main.command()
@vm_selection
@click.option("--keep-files", is_flag=True, help="keep VM folders on host")
@click.pass_obj
def delete(host: Host, vms: tuple[str, ...], devices: tuple[str, ...], all_: bool, keep_files: bool) -> None:
    """Delete VMs from libvirt (and their files unless --keep-files)."""
    spec.delete(host, *select_vms(host, vms, devices, all_), keep_files=keep_files)


@main.group("list")
def list_() -> None:
    """Show VMs or VNets on host (running in green; VNet devices "-" = not managed by vlab)."""


@list_.command("vms")
@click.pass_obj
def list_vms(host: Host) -> None:
    table = Table("name", "device", "interfaces", "disks")
    for vm, active in virt.list_vms(host):
        ifaces = ", ".join(f"net({i.network})" if i.network else f"br({i.bridge})" for i in vm.interfaces)
        table.add_row(vm.name, vm.device or "", ifaces, "\n".join(vm.disks), style="green" if active else "")
    Console().print(table)


@list_.command("vnets")
@click.pass_obj
def list_vnets(host: Host) -> None:
    table = Table("name", "devices", "bridge", "forward", "ip")
    for vnet, active in virt.list_vnets(host):
        table.add_row(
            vnet.name, "-" if vnet.devices is None else ", ".join(vnet.devices), vnet.bridge or "", vnet.forward or "", vnet.ip or "",
            style="green" if active else "",
        )
    Console().print(table)
