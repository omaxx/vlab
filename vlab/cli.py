from __future__ import annotations

from typing import Optional, List, Tuple
from importlib.metadata import version
import logging

import click
from rich.console import Console
from rich.logging import RichHandler

from .vhost import VHost
from .topology import Topology

console = Console()

logger = logging.getLogger("vlab")
logger.setLevel(logging.INFO)
logger.addHandler(RichHandler())


@click.group()
@click.pass_context
@click.option("--ip", "-i", help="KVM ip address", required=True)
@click.option("--topology", "-t", help="Topology file", required=True)
@click.option("--path", help="vhost: vLAB path")
@click.option("--images", help="vhost: images path")
def cli(
    ctx: click.Context, 
    ip: Optional[str],
    topology: Optional[str],
    path: Optional[str] = None,
    images: Optional[str] = None,
):
    ctx.ensure_object(dict)
    ctx.obj['VHOST'] = VHost(ip=ip, path=path, images=images)
    ctx.obj['topology'] = Topology.load(topology) if topology is not None else None


@cli.command(help="Display state of topology, devices and vms")
@click.pass_context
def state(ctx: click.Context):
    vhost: VHost = ctx.obj['VHOST']
    topology = ctx.obj['topology']
    vhost.fetch_state(topology, console)


@cli.command(help="Define topology")
@click.pass_context
def define(ctx: click.Context):
    vhost: VHost = ctx.obj['VHOST']
    topology = ctx.obj['topology']
    vhost.define(topology, console)


@cli.command(help="Undefine topology")
@click.pass_context
@click.option("--delete", "-d", is_flag=True, show_default=True, default=False, help="Delete images")
def undefine(ctx: click.Context, delete: bool):
    vhost: VHost = ctx.obj['VHOST']
    topology = ctx.obj['topology']
    vhost.undefine(topology, delete, console)


@cli.command(help="Start device")
@click.pass_context
@click.argument("devices", nargs=-1)
def start(ctx: click.Context, devices: Tuple[str, ...]):
    vhost: VHost = ctx.obj['VHOST']
    topology = ctx.obj['topology']
    vhost.start(topology, devices, console)


@cli.command(help="Stop device")
@click.pass_context
@click.argument("devices", nargs=-1)
def stop(ctx: click.Context, devices: Tuple[str, ...]):
    vhost: VHost = ctx.obj['VHOST']
    topology = ctx.obj['topology']
    vhost.stop(topology, devices, console)



# @cli.command(help="Create topology")
# @click.pass_context
# @click.argument("topology")
# def create(ctx: click.Context, topology: str):
#     vhost: VHost = ctx.obj['VHOST']
#     topology = Topology.load(topology)
#     topology.create(vhost)
#
#
