# Setup Host

Debian 13, 96 vCPU / 188G RAM, KVM available (`/dev/kvm`, kvm_intel loaded). Root disk only 30G — put images on bigger storage if needed.

## Config host

### Disable swap

Currently no swap active (`/proc/swaps` empty, nothing in fstab, no zram).

```shell
# check
cat /proc/swaps
/usr/sbin/swapon --show
grep -i swap /etc/fstab
systemctl list-units --all --type=swap

# option 1: turn off now (until reboot)
sudo swapoff -a

# option 2: permanent — comment swap lines in fstab
sudo sed -i '/\sswap\s/s/^/#/' /etc/fstab

# option 3: mask systemd swap units (e.g. auto-detected partitions)
sudo systemctl mask swap.target

# option 4: keep swap, but avoid using it
echo 'vm.swappiness=1' | sudo tee /etc/sysctl.d/99-swappiness.conf
sudo sysctl --system
```

### VLAB folders

Owner `$USER`, group `kvm` (primary group of `libvirt-qemu`, which runs VMs). Setgid keeps `kvm` on new files.

```shell
# create
sudo mkdir -p /var/lib/vlab/images
sudo mkdir -p /var/lib/vlab/vms

# permissions
sudo chown -R $USER:kvm /var/lib/vlab
sudo chmod -R 2775 /var/lib/vlab

# check
ls -ld /var/lib/vlab /var/lib/vlab/*
```

## Install qemu / libvirt

```shell
# check
egrep -c '(vmx|svm)' /proc/cpuinfo
ls -l /dev/kvm

# install
sudo apt update
sudo apt install -y --no-install-recommends \
  qemu-system-x86 \
  qemu-utils \
  ovmf \
  libvirt-daemon-system \
  libvirt-clients \
  virtinst \
  dnsmasq-base \
  swtpm-tools \
  genisoimage

# allow non-root use (re-login after)
sudo usermod -aG libvirt,kvm $USER
echo 'export LIBVIRT_DEFAULT_URI=qemu:///system' >> ~/.bashrc
[ -f ~/.zshrc ] && echo 'export LIBVIRT_DEFAULT_URI=qemu:///system' >> ~/.zshrc

# enable + verify
sudo systemctl enable --now libvirtd
virt-host-validate qemu
virsh list --all

# remove default NAT network (virbr0)
virsh net-destroy default
virsh net-autostart --disable default
virsh net-undefine default
virsh net-list --all
```

## Download images

```shell
# create
mkdir -p ~/downloads

# debian 13 cloud image
wget -N -P ~/downloads https://cloud.debian.org/images/cloud/trixie/latest/debian-13-genericcloud-amd64.qcow2
wget -N -P ~/downloads https://cloud.debian.org/images/cloud/trixie/latest/SHA512SUMS
grep ' debian-13-genericcloud-amd64.qcow2$' ~/downloads/SHA512SUMS | sed "s|  |  $HOME/downloads/|" | sha512sum -c

# copy to images
cp ~/downloads/debian-13-genericcloud-amd64.qcow2 /var/lib/vlab/images/
ls -l /var/lib/vlab/images
```

## Create management network

NAT to internet (no DHCP), bridge `mgmt-1`, host IP `172.255.1.254/24` = VM gateway + DNS (dnsmasq). No autostart.

```shell
# define
cat > /tmp/mgmt-1.xml <<'XML'
<network>
  <name>mgmt-1</name>
  <forward mode='nat'/>
  <bridge name='mgmt-1' stp='off' delay='0'/>
  <ip address='172.255.1.254' prefix='24'/>
</network>
XML
virsh net-define /tmp/mgmt-1.xml
rm /tmp/mgmt-1.xml

# start
virsh net-start mgmt-1
virsh net-list --all
ip -br a show mgmt-1
```

## Create p2p networks

Isolated L2 bridges `p2p-1`, `p2p-2`, no host IP. No autostart.

```shell
# define
cat > /tmp/p2p-1.xml <<'XML'
<network>
  <name>p2p-1</name>
  <bridge name='p2p-1' stp='off' delay='0'/>
</network>
XML
cat > /tmp/p2p-2.xml <<'XML'
<network>
  <name>p2p-2</name>
  <bridge name='p2p-2' stp='off' delay='0'/>
</network>
XML
virsh net-define /tmp/p2p-1.xml
virsh net-define /tmp/p2p-2.xml
rm /tmp/p2p-1.xml
rm /tmp/p2p-2.xml

# start
virsh net-start p2p-1
virsh net-start p2p-2
virsh net-list --all
ip -br a show p2p-1
ip -br a show p2p-2
```

## Create VM

`vm-$id`: 1 vCPU, 4G RAM, UEFI (BIOS boot loops on this host), qcow2 overlay on base image + cloud-init seed. All files in `vms/vm-$id`.
`id` = 2 digits (01-99), `n` = id w/o leading zero for IPs.
NICs (MAC `c0:ff:ee:<id>:00:0N`): `mgmt-1` 172.255.1.$n/24, `p2p-1` 192.168.1.$n/24, `p2p-2` 192.168.2.$n/24.

```shell
# vars
id=01
name=vm-$id
dir=/var/lib/vlab/vms/$name
n=$((10#$id))
mac=c0:ff:ee:$id:00

# folder + disk (copy-on-write overlay, base image must stay unchanged)
mkdir -p $dir
qemu-img create -f qcow2 -F qcow2 -b /var/lib/vlab/images/debian-13-genericcloud-amd64.qcow2 $dir/$name.qcow2

# cloud-init: meta-data
cat > $dir/meta-data <<EOT
instance-id: $name
local-hostname: $name
EOT

# cloud-init: user-data (user $USER, keys from id_*.pub + authorized_keys)
cat > $dir/user-data <<EOT
#cloud-config
users:
  - name: $USER
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
EOT
cat ~/.ssh/id_*.pub ~/.ssh/authorized_keys | sed 's/.*/      - "&"/' >> $dir/user-data

# cloud-init: network-config (v2)
cat > $dir/network-config <<EOT
version: 2
ethernets:
  mgmt:
    match: {macaddress: "$mac:01"}
    addresses: [172.255.1.$n/24]
    routes: [{to: default, via: 172.255.1.254}]
    nameservers: {addresses: [172.255.1.254]}
  p2p1:
    match: {macaddress: "$mac:02"}
    addresses: [192.168.1.$n/24]
  p2p2:
    match: {macaddress: "$mac:03"}
    addresses: [192.168.2.$n/24]
EOT

# cloud-init: seed iso
cloud-localds -N $dir/network-config $dir/seed.iso $dir/user-data $dir/meta-data

# create
virt-install \
  --name $name \
  --vcpus 1 \
  --memory 4096 \
  --osinfo debian13 \
  --boot uefi \
  --import \
  --disk $dir/$name.qcow2,bus=virtio \
  --disk $dir/seed.iso,device=cdrom \
  --network network=mgmt-1,model=virtio,mac=$mac:01 \
  --network network=p2p-1,model=virtio,mac=$mac:02 \
  --network network=p2p-2,model=virtio,mac=$mac:03 \
  --graphics none \
  --noautoconsole

# check
virsh list --all
virsh domiflist $name
ping -c 3 172.255.1.$n
ssh 172.255.1.$n hostname
ssh 172.255.1.$n sudo apt update
```

## Delete VM

```shell
# vars
id=01
name=vm-$id
n=$((10#$id))

# delete (--nvram: UEFI vars file)
virsh destroy $name
virsh undefine $name --nvram
rm -r /var/lib/vlab/vms/$name
ssh-keygen -R 172.255.1.$n
```
