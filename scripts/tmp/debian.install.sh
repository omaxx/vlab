#!/bin/bash
set -e

export ID=1

export VLAB=/var/vlab

test -d ${VLAB} || sudo mkdir ${VLAB}
test -d ${VLAB}/_boot_ || sudo mkdir ${VLAB}/_boot_

export DEV=srv-${ID}

sudo mkdir ${VLAB}/${DEV}

export IMG=/mnt/soft/linux/
export CDROM=debian-12.1.0-amd64-netinst.iso

echo "copy ${CDROM}"
test -f ${VLAB}/_boot_/${CDROM}  || sudo rsync -ah --progress ${IMG}/${CDROM} ${VLAB}/_boot_

virt-install \
    --name ${DEV} \
    --virt-type kvm \
    --os-variant debian12 \
    --memory 1024 \
    --vcpus=1 \
    --cdrom ${VLAB}/_boot_/${CDROM} \
    --disk size=10 \
    --network=bridge:mgmt,model=virtio \
    --network=bridge:srv1,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --graphics vnc,port=590${ID},listen=0.0.0.0 \
    &
