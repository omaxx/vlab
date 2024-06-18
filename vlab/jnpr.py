from __future__ import annotations

from typing import List, Optional

from .topology import VM, Device, VNet, Interface


def vmx(
    device_id: int,
    name: str,
    images: str,
    re_image: str,
    fpc_image: str,
    interfaces: List[Interface],
    re_vcpu: int = 1,
    re_memory: int = 1024,
    re_num: int = 1,
    fpc_vcpu: int = 3,
    fpc_memory: int = 2048,
    fpc_num: int = 1,
) -> Device:
    return Device(
        name=name,
        vms=[
            VM(
                name=f"{name}~re{slot}",
                xml="jnpr-vmx-re",
                path=f"{name}/re{slot}",
                vcpu=re_vcpu,
                memory=re_memory,
                src=images,
                images=[
                    re_image,
                    "vmxhdd.img",
                    f"metadata-usb-re{slot}.img",
                ],
                interfaces=[

                ],
                device_id=device_id,
                device_name=name,
                slot=slot,
            ) for slot in range(re_num)
        ] + [
            VM(
                name=f"{name}~fpc{slot}",
                xml="jnpr-vmx-fpc",
                path=f"{name}/fpc{slot}",
                vcpu=fpc_vcpu,
                memory=fpc_memory,
                src=images,
                images=[
                    fpc_image,
                    f"metadata-usb-fpc{slot}.img",
                ],
                interfaces=[
                    *interfaces,
                ],
                device_id=device_id,
                device_name=name,
                slot=slot,
            ) for slot in range(fpc_num)
        ],
        vnets=[
            VNet(name=f"{name}~int"),
        ],
        interfaces=interfaces,
    )


def vqfx(
    device_id: int,
    name: str,
    images: str,
    re_image: str,
    pfe_image: str,
    interfaces: List[Interface],
    re_vcpu: int = 1,
    re_memory: int = 1024,
    re_num: int = 1,
    pfe_vcpu: int = 1,
    pfe_memory: int = 1024,
    pfe_num: int = 1,
) -> Device:
    return Device(
        name=name,
        vms=[
            VM(
                name=f"{name}~re{slot}",
                xml="jnpr-vqfx-re",
                path=f"{name}/re{slot}",
                vcpu=re_vcpu,
                memory=re_memory,
                src=images,
                images=[
                    re_image,
                ],
                interfaces=[
                ],
                device_id=device_id,
                device_name=name,
                slot=slot,
            ) for slot in range(re_num)
        ] + [
            VM(
                name=f"{name}~pfe{slot}",
                xml="jnpr-vqfx-pfe",
                path=f"{name}/pfe{slot}",
                vcpu=pfe_vcpu,
                memory=pfe_memory,
                src=images,
                images=[
                    pfe_image,
                ],
                interfaces=[
                    *interfaces,
                ],
                device_id=device_id,
                device_name=name,
                slot=slot,
            ) for slot in range(pfe_num)
        ],
        vnets=[
            VNet(name=f"{name}~int"),
            VNet(name=f"{name}~res"),
        ],
        interfaces=interfaces,
    )


def vsrx(
    device_id: int,
    name: str,
    images: str,
    image: str,
    interfaces: List[Interface],
    vcpu: int = 1,
    memory: int = 1024,
) -> Device:
    return Device(
        name=name,
        vms=[
            VM(
                name=f"{name}",
                xml="jnpr-vsrx",
                path=f"{name}",
                vcpu=vcpu,
                memory=memory,
                src=images,
                images=[
                    image,
                ],
                interfaces=[
                    *interfaces,
                ],
                device_id=device_id,
                device_name=name,
            )
        ],
        vnets=[],
        interfaces=interfaces,
    )
