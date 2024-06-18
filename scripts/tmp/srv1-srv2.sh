#!/bin/bash
set -e

ID=2
VLAB=/var/vlab

umask 0002

test -d ${VLAB} \
    || sudo mkdir ${VLAB} \
    && sudo chown :libvirt ${VLAB} \
    && sudo chmod g+ws ${VLAB}

DEV=srv${ID}

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
        - type: static
          address: 192.168.1.6/24
    - type: physical
      name: enp2s0
      subnets:
        - type: static
          address: 172.31.2.1/24
    - type: physical
      name: enp3s0
      subnets:
        - type: dhcp
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
    --network=bridge:mgmt,model=virtio \
    --network=bridge:srv2,model=virtio \
    --network=bridge:vmbr0,model=virtio \
    --graphics vnc,port=590${ID},listen=0.0.0.0 \
    &
