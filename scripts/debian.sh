#!/bin/bash
set -e

ID=1
VLAB=/var/vlab

umask 0002

test -d ${VLAB} \
    || sudo mkdir ${VLAB} \
    && sudo chown :libvirt ${VLAB} \
    && sudo chmod g+ws ${VLAB}

DEV=srv-${ID}

mkdir ${VLAB}/${DEV}

IMG=/mnt/soft/linux/
HDD=debian-12-genericcloud-amd64-20240211-1654.qcow2

echo "copy ${HDD}"
rsync -h --progress --chmod=0664 ${IMG}/${HDD} ${VLAB}/${DEV}

USERNAME=$(id -un)
PASSWORD="User#123"

touch ${VLAB}/${DEV}/meta-data
cat >${VLAB}/${DEV}/network-config <<EOF
#network-config
network:
  version: 1
  config:
    - type: physical
      name: enp1s0
      subnets:
        - type: dhcp
    - type: physical
      name: enp1s1
      subnets:
        - type: static
          address: 172.31.1.${ID}/24
          gateway: 172.31.1.254
EOF

cat >${VLAB}/${DEV}/user-data <<EOF
#cloud-config
system_info:
  default_user:
    name: $USERNAME
    home: /home/$USERNAME

package_update: false
package_upgrade: false

password: $PASSWORD
ssh_pwauth: true
chpasswd: { expire: False }
hostname: $DEV
EOF

genisoimage \
    -output ${VLAB}/${DEV}/seed.img \
    -volid cidata \
    -rational-rock \
    -joliet \
    ${VLAB}/${DEV}/user-data ${VLAB}/${DEV}/meta-data ${VLAB}/${DEV}/network-config


virt-install \
    --name ${DEV} \
    --virt-type kvm \
    --os-variant debian12 \
    --memory 1024 \
    --vcpus=1 \
    --import \
    --disk path=${VLAB}/${DEV}/${HDD} \
    --disk path=${VLAB}/${DEV}/seed.img \
    --network=bridge:vmbr0,model=virtio \
    --network=bridge:vmbr1,model=virtio \
    --graphics vnc,port=590${ID},listen=0.0.0.0 \
    &
