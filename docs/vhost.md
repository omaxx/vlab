# vHost preparation

## Debian

### Network setup

### Instal packages

```bash
# Update system
sudo apt-get update && sudo apt-get -y upgrade

# Install qemu/kvm
sudo apt-get --no-install-recommends qemu-system libvirt-daemon-system libvirt-clients bridge-utils dnsmasq

# Install python libraries
sudo apt-get --no-install-recommends python3-libvirt python3-lxml
```

## AlmaLinux & Rocky Linux

### Instal packages

```bash
# Enable EPEL repo
sudo dnf install -y epel-release

# Install qemu/kvm
sudo dnf install -y qemu-kvm libvirtbridge-utils dnsmasq

# Start and enable libvirtd.socket
sudo systemctl enable --now libvirtd.socket

# Install python libraries
sudo dnf install -y python3-libvirt python3-lxml
```
