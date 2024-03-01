#!/bin/bash
set -e

VLAB=/var/vlab

umask 0002

test -d ${VLAB} \
    || sudo mkdir ${VLAB} \
    && sudo chown :libvirt ${VLAB} \
    && sudo chmod g+ws ${VLAB}

DEV=vqfx-1

mkdir ${VLAB}/${DEV}
mkdir ${VLAB}/${DEV}/re
mkdir ${VLAB}/${DEV}/pfe

IMG=/mnt/soft/junos/vqfx/20.2

rsync -h --progress --chmod=0664 ${IMG}/vqfx-20.2R1.10-re-qemu.qcow2 ${VLAB}/${DEV}/re

rsync -h --progress --chmod=0664 ${IMG}/vqfx-20.2R1-2019010209-pfe-qemu.qcow ${VLAB}/${DEV}/pfe

cat <<EOF > ${DEV}-int.xml
<network>
  <name>${DEV}-int</name>
  <bridge name='${DEV}-int' stp='off' delay='0'/>
</network>
EOF

virsh net-define ${DEV}-int.xml
virsh net-start ${DEV}-int

cat <<EOF > ${DEV}-res.xml
<network>
  <name>${DEV}-res</name>
  <bridge name='${DEV}-res' stp='off' delay='0'/>
</network>
EOF

virsh net-define ${DEV}-res.xml
virsh net-start ${DEV}-res

virt-install \
    --name ${DEV}-re \
    --osinfo detect=on,require=off \
    --memory 1024 \
    --vcpus=1 \
    --import \
    --disk path=${VLAB}/${DEV}/re/vqfx-20.2R1.10-re-qemu.qcow2,bus=ide,format=qcow2 \
    --network=bridge:vmbr0,model=virtio \
    --network=network:${DEV}-int,model=virtio \
    --network=network:${DEV}-res,model=virtio \
    --graphics none \
    &


virt-install \
    --name ${DEV}-fpc \
    --osinfo detect=on,require=off \
    --memory 2048 \
    --vcpus=1 \
    --import \
    --disk path=${VLAB}/${DEV}/pfe/vqfx-20.2R1-2019010209-pfe-qemu.qcow \
    --network=bridge:vmbr0,model=virtio \
    --network=network:${DEV}-int,model=virtio \
    --network=network:${DEV}-res,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --graphics none \
    &
