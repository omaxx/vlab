import logging

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from . import spec, virt
from .host import Host
from .spec import Debian
from .utils import load_file

LOG_LEVELS = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}


@click.group()
@click.option("-v", "--verbose", count=True, help="-v: info, -vv: debug")
@click.pass_context
def main(ctx: click.Context, verbose: int) -> None:
    """Virtual lab on libvirt."""
    logging.basicConfig(
        level=LOG_LEVELS[min(verbose, 2)], format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
    )
    ctx.obj = Host()


spec_file = click.option(
    "-f", "--file", "path", required=True, type=click.Path(exists=True, dir_okay=False),
    help="node spec: .yaml, .json or .jsonnet",
)


@main.command()
@spec_file
@click.option("--overwrite", is_flag=True, help="rewrite existing VM files instead of keeping them")
@click.pass_obj
def deploy(host: Host, path: str, overwrite: bool) -> None:
    """Define node VNets and VMs on host (not started)."""
    node = Debian.from_dict(load_file(path))
    node.deploy(host, overwrite=overwrite)
    click.echo(f"{node.name} defined")


def select_vms(host: Host, vms: tuple[str, ...], nodes: tuple[str, ...], all_: bool) -> list[str]:
    """VM names: given VM names + VMs of given nodes; --all = every VM with vlab metadata."""
    if not (vms or nodes or all_):
        raise click.UsageError("give VM names, --node or --all")
    selected = list(vms)
    for vm, _ in virt.list_vms(host):
        if vm.node is not None and (all_ or vm.node in nodes) and vm.name not in selected:
            selected.append(vm.name)
    return selected


def vm_selection(f):
    f = click.argument("vms", nargs=-1)(f)
    f = click.option("-n", "--node", "nodes", multiple=True, help="all VMs of node (repeatable)")(f)
    f = click.option("--all", "all_", is_flag=True, help="all VMs managed by vlab")(f)
    return f


@main.command()
@vm_selection
@click.pass_obj
def start(host: Host, vms, nodes, all_) -> None:
    """Start VMs and their vlab VNets."""
    virt.start_vms(host, *select_vms(host, vms, nodes, all_))


@main.command()
@vm_selection
@click.pass_obj
def stop(host: Host, vms, nodes, all_) -> None:
    """Force off VMs, stop vlab VNets no longer used."""
    virt.stop_vms(host, *select_vms(host, vms, nodes, all_))


@main.command()
@vm_selection
@click.option("--keep-files", is_flag=True, help="keep VM folders on host")
@click.pass_obj
def delete(host: Host, vms, nodes, all_, keep_files: bool) -> None:
    """Delete VMs from libvirt (and their files unless --keep-files)."""
    spec.delete(host, *select_vms(host, vms, nodes, all_), keep_files=keep_files)


@main.group("list")
def list_() -> None:
    """Show VMs or VNets on host (running in green)."""


@list_.command("vms")
@click.pass_obj
def list_vms(host: Host) -> None:
    table = Table("name", "node", "interfaces", "disks")
    for vm, active in virt.list_vms(host):
        ifaces = ", ".join(f"net({i.network})" if i.network else f"br({i.bridge})" for i in vm.interfaces)
        table.add_row(vm.name, vm.node or "", ifaces, "\n".join(vm.disks), style="green" if active else "")
    Console().print(table)


@list_.command("vnets")
@click.pass_obj
def list_vnets(host: Host) -> None:
    table = Table("name", "nodes", "bridge", "forward", "ip")
    for vnet, active in virt.list_vnets(host):
        table.add_row(
            vnet.name, ", ".join(vnet.nodes), vnet.bridge or "", vnet.forward or "", vnet.ip or "",
            style="green" if active else "",
        )
    Console().print(table)
