#!/bin/bash
set -e

export VLAB=/var/vlab

test -d ${VLAB} || sudo mkdir ${VLAB}

export DEV=vsrx-1

sudo mkdir ${VLAB}/${DEV}

export IMG=/mnt/soft/junos/vsrx/21.4R3-S4

echo "copy ${DEV} images"
sudo rsync -ah --progress ${IMG}/junos-media-vsrx-x86-64-vmdisk-21.4R3-S4.9.qcow2 ${VLAB}/${DEV}

virt-install \
    --name ${DEV} \
    --osinfo detect=on,require=off \
    --vcpus=2 \
    --memory 4096 \
    --import \
    --disk path=${VLAB}/${DEV}/junos-media-vsrx-x86-64-vmdisk-21.4R3-S4.9.qcow2,bus=ide,format=qcow2 \
    --network=bridge:vmbr0,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --graphics none \
    &
