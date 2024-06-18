#!/bin/bash
set -e

VLAB=/var/vlab

umask 0002

test -d ${VLAB} \
    || sudo mkdir ${VLAB} \
    && sudo chown :libvirt ${VLAB} \
    && sudo chmod g+ws ${VLAB}

DEV=vsrx-1

mkdir ${VLAB}/${DEV}

IMG=/mnt/soft/junos/vsrx3

echo "copy ${DEV} images"
rsync -h --progress --chmod=0664 ${IMG}/junos-vsrx3-x86-64-23.2R1-S2.5.qcow2 ${VLAB}/${DEV}

virt-install \
    --name ${DEV} \
    --osinfo detect=on,require=off \
    --vcpus=2 \
    --memory 4096 \
    --import \
    --disk path=${VLAB}/${DEV}/junos-vsrx3-x86-64-23.2R1-S2.5.qcow2,bus=ide,format=qcow2 \
    --network=bridge:mgmt,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --network=bridge:vmbr1,model=virtio \
    --network=bridge:vmbr2,model=virtio \
    --graphics none \
    &
