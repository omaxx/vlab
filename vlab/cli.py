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
@click.option("--ip", help="KVM ip address")
def cli(ctx: click.Context, ip: Optional[str] = None):
    ctx.ensure_object(dict)
    ctx.obj['VHOST'] = VHost(ip=ip)


@cli.command(help="Display state of topology, devices and vms")
@click.pass_context
@click.argument("topology")
def state(ctx: click.Context, topology: str):
    vhost: VHost = ctx.obj['VHOST']
    topology = Topology.load(topology)
    vhost.fetch_state(topology, console)


@cli.command(help="Define topology")
@click.pass_context
@click.argument("topology")
def define(ctx: click.Context, topology: str):
    vhost: VHost = ctx.obj['VHOST']
    topology = Topology.load(topology)
    vhost.define(topology, console)


@cli.command(help="Undefine topology")
@click.pass_context
@click.argument("topology")
@click.option("--delete", "-d", is_flag=True, show_default=True, default=False, help="Delete images")
def undefine(ctx: click.Context, topology: str, delete: bool):
    vhost: VHost = ctx.obj['VHOST']
    topology = Topology.load(topology)
    vhost.undefine(topology, delete, console)


@cli.command(help="Start device")
@click.pass_context
@click.argument("topology")
@click.argument("devices", nargs=-1)
def start(ctx: click.Context, topology: str, devices: Tuple[str, ...]):
    vhost: VHost = ctx.obj['VHOST']
    topology = Topology.load(topology)
    vhost.start(topology, devices, console)


@cli.command(help="Stop device")
@click.pass_context
@click.argument("topology")
@click.argument("devices", nargs=-1)
def stop(ctx: click.Context, topology: str, devices: Tuple[str, ...]):
    vhost: VHost = ctx.obj['VHOST']
    topology = Topology.load(topology)
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
