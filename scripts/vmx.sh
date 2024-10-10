#!/bin/bash
set -e

LIBVIRT_DEFAULT_URI="qemu:///system"
VLAB=/var/vlab

umask 0002

test -d ${VLAB} \
    || sudo mkdir ${VLAB} \
    && sudo chown :libvirt ${VLAB} \
    && sudo chmod g+ws ${VLAB}

DEV=vmx-1

mkdir ${VLAB}/${DEV}
mkdir ${VLAB}/${DEV}/re0
mkdir ${VLAB}/${DEV}/re1
mkdir ${VLAB}/${DEV}/fpc0
# mkdir ${VLAB}/${DEV}/fpc1

IMG=/var/soft/junos/vmx/23.2R2-S1.3/images/
RE_IMG=junos-vmx-x86-64-23.2R2-S1.3.qcow2
FPC_IMG=vFPC-20240508.img

echo "copy ${DEV}/re0 images"
rsync -h --progress --chmod=0664 ${IMG}/${RE_IMG} ${VLAB}/${DEV}/re0
rsync -h --progress --chmod=0664 ${IMG}/vmxhdd.img ${VLAB}/${DEV}/re0
rsync -h --progress --chmod=0664 ${IMG}/metadata-usb-re0.img ${VLAB}/${DEV}/re0

echo "copy ${DEV}/re1 images"
rsync -h --progress --chmod=0664 ${IMG}/${RE_IMG} ${VLAB}/${DEV}/re1
rsync -h --progress --chmod=0664 ${IMG}/vmxhdd.img ${VLAB}/${DEV}/re1
rsync -h --progress --chmod=0664 ${IMG}/metadata-usb-re1.img ${VLAB}/${DEV}/re1

echo "copy ${DEV}/fpc0 images"
rsync -h --progress --chmod=0664 ${IMG}/${FPC_IMG} ${VLAB}/${DEV}/fpc0
rsync -h --progress --chmod=0664 ${IMG}/metadata-usb-fpc0.img ${VLAB}/${DEV}/fpc0

# echo "copy ${DEV}/fpc1 images"
# rsync -h --progress --chmod=0664 ${IMG}/vFPC-20240508.img ${VLAB}/${DEV}/fpc1
# rsync -h --progress --chmod=0664 ${IMG}/metadata-usb-fpc1.img ${VLAB}/${DEV}/fpc1

cat <<EOF > ${DEV}-int.xml
<network>
  <name>${DEV}-int</name>
  <bridge name='${DEV}-int' stp='off' delay='0'/>
</network>
EOF

virsh net-define ${DEV}-int.xml
virsh net-start ${DEV}-int

virt-install \
    --name ${DEV}-re0 \
    --osinfo detect=on,require=off \
    --memory 1024 \
    --vcpus=1 \
    --import \
    --disk path=${VLAB}/${DEV}/re0/${RE_IMG},bus=ide,format=qcow2 \
    --disk path=${VLAB}/${DEV}/re0/vmxhdd.img,bus=ide,format=qcow2 \
    --disk path=${VLAB}/${DEV}/re0/metadata-usb-re0.img,bus=ide,format=raw \
    --network=bridge:vmbr0,model=virtio \
    --network=network:${DEV}-int,model=virtio \
    --graphics none \
    &

virt-install \
    --name ${DEV}-re1 \
    --osinfo detect=on,require=off \
    --memory 1024 \
    --vcpus=1 \
    --import \
    --disk path=${VLAB}/${DEV}/re1/${RE_IMG},bus=ide,format=qcow2 \
    --disk path=${VLAB}/${DEV}/re1/vmxhdd.img,bus=ide,format=qcow2 \
    --disk path=${VLAB}/${DEV}/re1/metadata-usb-re1.img,bus=ide,format=raw \
    --network=bridge:vmbr0,model=virtio \
    --network=network:${DEV}-int,model=virtio \
    --graphics none \
    &

virt-install \
    --name ${DEV}-fpc0 \
    --osinfo detect=on,require=off \
    --memory 4096 \
    --vcpus=3 \
    --import \
    --disk path=${VLAB}/${DEV}/fpc0/${FPC_IMG},bus=ide,format=raw \
    --disk path=${VLAB}/${DEV}/fpc0/metadata-usb-fpc0.img,bus=ide,format=raw \
    --network=bridge:vmbr0,model=virtio \
    --network=network:${DEV}-int,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --graphics none \
    &
    
# virt-install \
#     --name ${DEV}-fpc1 \
#     --osinfo detect=on,require=off \
#     --memory 4096 \
#     --vcpus=3 \
#     --import \
#     --disk path=${VLAB}/${DEV}/fpc1/vFPC-20230502.img,bus=ide,format=raw \
#     --disk path=${VLAB}/${DEV}/fpc1/metadata-usb-fpc1.img,bus=ide,format=raw \
#     --network=bridge:vmbr0,model=virtio \
#     --network=network:${DEV}-int,model=virtio \
#     --network=bridge:vmbr0,model=virtio \
#     --network=bridge:vmbr0,model=virtio \
#     --network=bridge:vmbr0,model=virtio \
#     --network=bridge:vmbr0,model=virtio \
#     --graphics none \
#     &
    