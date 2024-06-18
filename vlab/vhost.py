from __future__ import annotations

from typing import Optional, Union, ClassVar, List, Self, Dict, Tuple

import logging
from pathlib import Path
from importlib import resources

import libvirt
import fabric
from rich.console import Console
import jinja2

from .topology import Topology, VM

FWD_MASK = "0xfff8"

logger = logging.getLogger(__name__)
jinja = jinja2.Environment(undefined=jinja2.StrictUndefined)


class VHost:
    PATH: ClassVar[str] = "/home/vlab"
    IMAGES: ClassVar[str] = "/mnt/soft"

    def __init__(
        self,
        ip: Optional[str] = None,
        path: Union[str, Path, None] = None,
        images: Union[str, Path, None] = None,
    ):
        self.path: Union[str, Path] = path or self.PATH
        if not isinstance(self.path, Path):
            self.path = Path(self.path)
        self.path.expanduser()

        self.images: Union[str, Path] = images or self.IMAGES
        if not isinstance(self.images, Path):
            self.images = Path(self.images)
        self.images.expanduser()

        self.fabric = fabric.Connection(ip)
        try:
            self.fabric.run(
                f"test -d { self.path } "
                f"|| sudo mkdir { self.path } "
                f"&& sudo chown :libvirt { self.path } "
                f"&& sudo chmod g+ws { self.path }"
            )
        except Exception as exc:
            logger.critical(f"{exc.__class__.__name__}: {exc}")
            raise SystemExit(1)

        self.qemu: Optional[libvirt.virConnect] = None
        try:
            if ip is None:
                self.qemu = libvirt.open("qemu:///system")
            else:
                self.qemu = libvirt.open(f"qemu+ssh://{ip}/system")
        except libvirt.libvirtError as exc:
            logger.critical(f"{exc.__class__.__name__}: {exc}")
            raise SystemExit(1)

    def __del__(self):
        if self.qemu is not None:
            self.qemu.close()

    def fetch_state(self, topology: Topology, console: Optional[Console] = None):
        vms = {vm.name(): vm for vm in self.qemu.listAllDomains(0)}
        vnets = {vnet.name(): vnet for vnet in self.qemu.listAllNetworks(0)}

        for device in topology.devices:
            for vm in device.vms:
                if vm.name in vms:
                    vm.state = VM.State(vms[vm.name].state()[0])
                else:
                    vm.state = VM.State.ABSEND

                for image in vm.images:
                    image.exist = self.fabric.run(f"test -f {self.path / vm.path / image.path}", warn=True).ok

            for vnet in device.vnets:
                if vnet.name in vnets:
                    vnet.state = vnets[vnet.name].isActive()
                else:
                    vnet.state = -1

            if console is not None:
                console.print(device)

        for vnet in topology.vnets:
            if vnet.name in vnets:
                vnet.state = vnets[vnet.name].isActive()
            else:
                vnet.state = -1

    def define(self, topology: Topology, console: Optional[Console] = None):
        vms = {vm.name(): vm for vm in self.qemu.listAllDomains(0)}
        vnets = {vnet.name(): vnet for vnet in self.qemu.listAllNetworks(0)}

        for vnet in topology.vnets:
            if vnet.name in vnets:
                logger.warning(f"VNet {vnet.name} already exist")
            else:
                try:
                    with (resources.files("vlab.xml") / f'{vnet.xml}.xml.j2').open() as io:
                        xml = jinja.from_string(io.read()).render(
                            vnet=vnet,
                            vhost=self,
                        )
                        self.qemu.networkDefineXML(xml)
                        logger.info(f"vnet {vnet.name} defined")
                except jinja2.exceptions.UndefinedError as exc:
                    logger.error(f"{vnet.xml}: {exc}")
                    raise SystemExit(1)

        for device in topology.devices:
            for vm in device.vms:
                path = self.path / vm.path
                self.fabric.run(f"test -d {path} || mkdir -p {path}")
                for image in vm.images:
                    image.exist = self.fabric.run(f"test -f {path / image.path}", warn=True).ok
                    if image.exist:
                        logger.warning(f"image {path / image.path} exist")
                    else:
                        logger.info(f"rsync {self.images / vm.src / image.path} to {path}")
                        self.fabric.run(
                            f"rsync -h --chmod=0664 {self.images / vm.src / image.path} {path}"
                        )
                        logger.info(f"rsync {self.images / vm.src / image.path} to {path}: DONE")

                if vm.name in vms:
                    logger.warning(f"VM {vm.name} already exist")
                else:
                    try:
                        with (resources.files("vlab.xml") / f'{vm.xml}.xml.j2').open() as io:
                            xml = jinja.from_string(io.read()).render(
                                vm=vm,
                                vhost=self,
                            )
                            self.qemu.defineXML(xml)
                            logger.info(f"define VM {vm.name}: DONE")
                    except (jinja2.exceptions.UndefinedError, libvirt.libvirtError) as exc:
                        logger.error(f"{exc.__class__.__name__}: {exc}")
                        logger.error(vm)
                        raise SystemExit(1)

            for vnet in device.vnets:
                if vnet.name in vnets:
                    logger.warning(f"VNet {vnet.name} already exist")
                else:
                    try:
                        with (resources.files("vlab.xml") / f'{vnet.xml}.xml.j2').open() as io:
                            xml = jinja.from_string(io.read()).render(
                                vnet=vnet,
                                vhost=self,
                            )
                            self.qemu.networkDefineXML(xml)
                            #
                            logger.info(f"vnet {vnet.name} defined")
                    except (jinja2.exceptions.UndefinedError, libvirt.libvirtError) as exc:
                        logger.error(f"{exc.__class__.__name__}: {exc}")
                        logger.error(vnet)
                        raise SystemExit(1)

    def start(self, topology: Topology, devices: Tuple[str, ...], console: Optional[Console] = None):
        for device_name in devices:
            if device_name not in [device.name for device in topology.devices]:
                logger.error(f"Device {device_name} not found")
                raise SystemExit(1)

        vms = {vm.name(): vm for vm in self.qemu.listAllDomains(0)}
        vnets = {vnet.name(): vnet for vnet in self.qemu.listAllNetworks(0)}

        for vnet in topology.vnets:
            if vnet.name not in vnets:
                logger.error(f"VNet {vnet.name} not exist")
                raise SystemExit(1)

            if not vnets[vnet.name].isActive():
                vnets[vnet.name].create()
                logger.info(f"VNet {vnet.name} started")
            self.fabric.run(f'sudo bash -c "echo {FWD_MASK} >/sys/class/net/{vnet.name}/bridge/group_fwd_mask"')

        for device in topology.devices:
            if devices == () or device.name in devices:
                for vnet in device.vnets:
                    if vnet.name not in vnets:
                        logger.error(f"VNet {vnet.name} not exist")
                        raise SystemExit(1)
                    if not vnets[vnet.name].isActive():
                        vnets[vnet.name].create()
                        logger.info(f"VNet {vnet.name} started")
                    self.fabric.run(f'sudo bash -c "echo {FWD_MASK} >/sys/class/net/{vnet.name}/bridge/group_fwd_mask"')

                for vm in device.vms:
                    if vm.name not in vms:
                        logger.error(f"VM {vm.name} not exist")
                        raise SystemExit(1)
                    if not vms[vm.name].isActive():
                        vms[vm.name].create()
                        logger.info(f"VM {vm.name} started")

    def stop(self, topology: Topology, devices: Tuple[str, ...], console: Optional[Console] = None):
        for device_name in devices:
            if device_name not in [device.name for device in topology.devices]:
                logger.error(f"Device {device_name} not found")
                raise SystemExit(1)

        vms = {vm.name(): vm for vm in self.qemu.listAllDomains(0)}
        vnets = {vnet.name(): vnet for vnet in self.qemu.listAllNetworks(0)}

        for device in topology.devices:
            if devices == () or device.name in devices:
                for vm in device.vms:
                    if vm.name not in vms:
                        logger.error(f"VM {vm.name} not exist")
                    elif vms[vm.name].isActive():
                        vms[vm.name].destroy()
                        logger.info(f"VM {vm.name} stopped")

                for vnet in device.vnets:
                    if vnet.name not in vnets:
                        logger.error(f"VNet {vnet.name} not exist")
                    elif vnets[vnet.name].isActive():
                        vnets[vnet.name].destroy()
                        logger.info(f"VNet {vnet.name} stopped")

        if devices == ():
            for vnet in topology.vnets:
                if vnet.name not in vnets:
                    logger.error(f"VNet {vnet.name} not exist")
                elif vnets[vnet.name].isActive():
                    vnets[vnet.name].destroy()
                    logger.info(f"VNet {vnet.name} stopped")

    def undefine(self, topology: Topology, delete: bool, console: Optional[Console] = None):
        vms = {vm.name(): vm for vm in self.qemu.listAllDomains(0)}
        vnets = {vnet.name(): vnet for vnet in self.qemu.listAllNetworks(0)}

        for device in topology.devices:
            for vm in device.vms:
                if vm.name not in vms:
                    logger.warning(f"VM {vm.name} not exist")
                else:
                    if vms[vm.name].isActive():
                        vms[vm.name].destroy()
                        logger.info(f"VM {vm.name} stopped")
                    vms[vm.name].undefine()
                    logger.info(f"VM {vm.name} undefined")

                if delete:
                    if self.fabric.run(f"test -d {self.path / vm.path}", warn=True).ok:
                        self.fabric.run(f"rm -rf {self.path / vm.path}")
                        logger.info(f"VM {vm.name} images deleted")

            for vnet in device.vnets:
                if vnet.name not in vnets:
                    logger.warning(f"VNet {vnet.name} not exist")
                else:
                    if vnets[vnet.name].isActive():
                        vnets[vnet.name].destroy()
                        logger.info(f"VNet {vnet.name} stopped")
                    vnets[vnet.name].undefine()
                    logger.info(f"VNet {vnet.name} undefined")

        for vnet in topology.vnets:
            if vnet.name not in vnets:
                logger.warning(f"VNet {vnet.name} not exist")
            else:
                if vnets[vnet.name].isActive():
                    vnets[vnet.name].destroy()
                    logger.info(f"VNet {vnet.name} stopped")
                vnets[vnet.name].undefine()
                logger.info(f"VNet {vnet.name} undefined")

        if delete:
            self.fabric.run(
                f'find {self.path} -type d -not -wholename "{self.path}"' ' -exec rm -rf {} +'
            )
            logger.info(f"vLAB deleted")
