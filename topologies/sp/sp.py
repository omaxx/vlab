#!/usr/bin/env python

from vlab.vhost import VHost
from vlab.topology import Topology, network
from vlab import jnpr

import click

vhost = VHost(ip="172.31.0.8", path="/home/vlab")

vmx_options = dict(
    images="junos/vmx/23.2R2/images",
    re_image="junos-vmx-x86-64-23.2R2.21.qcow2",
    fpc_image="vFPC-20240301.img",
)

vqfx_options = dict(
    images="junos/vqfx/20.2",
    re_image="vqfx-20.2R1.10-re-qemu.qcow2",
    pfe_image="vqfx-20.2R1-2019010209-pfe-qemu.qcow",
)

vsrx_options = dict(
    images="junos/vsrx",
    image="junos-media-vsrx-x86-64-vmdisk-22.4R2-S2.6.qcow2",
)

vsrx3_options = dict(
    images="junos/vsrx3",
    image="junos-vsrx3-x86-64-23.2R1-S2.5.qcow2",
)

topology = Topology(
    devices=[
        jnpr.vmx(1, "R1", interfaces=[
            network("R1_R9"),
            network("R1_R2"),
            network("R1_R3"),
            network("R1_R4"),
        ], **vmx_options),
        jnpr.vmx(2, "R2", interfaces=[
            network("R1_R2"),
            network("R2_R3"),
            network("R2_R8"),
            network("R2_R5"),
        ], **vmx_options),
        jnpr.vmx(3, "R3", interfaces=[
            network("R2_R3"),
            network("R3_R4"),
            network("R3_R7"),
            network("R3_R7"),
        ], **vmx_options),
        jnpr.vmx(4, "R4", interfaces=[
            network("R3_R4"),
            network("R4_R5"),
            network("R1_R4"),
            network("R4_R6"),
        ], **vmx_options),
        jnpr.vmx(5, "R5", interfaces=[
            network("R4_R5"),
            network("R5_R6"),
            network("R2_R5"),
            network("R5_R8"),
        ], **vmx_options),
        jnpr.vmx(6, "R6", interfaces=[
            network("R5_R6"),
            network("R6_R7"),
            network("R4_R6"),
            network("R6_R9"),
        ], **vmx_options),
        jnpr.vmx(7, "R7", interfaces=[
            network("R6_R7"),
            network("R7_R8"),
            network("R7_R9"),
            network("R3_R7"),
        ], **vmx_options),
        jnpr.vmx(8, "R8", interfaces=[
            network("R7_R8"),
            network("R8_R9"),
            network("R5_R8"),
            network("R2_R8"),
        ], **vmx_options),
        jnpr.vmx(9, "R9", interfaces=[
            network("R8_R9"),
            network("R1_R9"),
            network("R6_R9"),
            network("R7_R9"),
        ], **vmx_options),
    ]
)


@click.group()
def cli():
    pass


@cli.command()
def status():
    for device in topology.devices:
        print(device.name)

    for vnet in topology.vnets:
        print(vnet.name)


@cli.command()
def create():
    topology.create(vhost)


@cli.command()
def destroy():
    topology.destroy(vhost)


@cli.command()
def delete():
    topology.delete(vhost)


cli()
