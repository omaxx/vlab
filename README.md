# vlab

Virtual lab on libvirt/QEMU. Lab specs (YAML, JSON or Jsonnet) are deployed to a host:

- **Network** spec → one libvirt network (VNet)
- **Device** spec (`type: linux`, ...) → one or more VMs + internal VNets

vlab tags what it creates with libvirt `<metadata>` and only starts/stops VNets it manages:
a managed VNet starts with its first VM and stops when no running VM uses it.

Host setup (KVM, libvirt, base images): see [VLAB.md](VLAB.md).

## Install

```shell
uv sync
```

## Specs

`topology/test.yaml/mgmt-1.yaml` — NAT network, host IP = VM gateway/DNS:

```yaml
name: mgmt-1
ip: 172.255.1.254/24
forward: nat
# mtu: 9000              # optional, default 1500
# dhcp:                  # optional ranges / fixed hosts; devices add their own (port dhcp: true)
#   ranges: [{start: 172.255.1.100, end: 172.255.1.199}]
```

`forward: bridge` + `bridge: br0` wraps an existing host bridge as a network (no ip/dhcp/mtu).

`topology/test.yaml/vm-1.yaml` — Linux cloud image VM (image in `/var/lib/vlab/images/linux/`), configured by cloud-init:

```yaml
type: linux               # device type, required
name: vm-01
id: 1                     # MACs ca:ff:ee:01:00:<port>, host ifnames vm-01-<port>
user: $USER
ssh_key_files:
  - ~/.ssh/id_ed25519.pub
ports:
  - network: mgmt-1
    ip: 172.255.1.1/24
    gateway: 172.255.1.254
    dns: [172.255.1.254]
    dhcp: true            # fixed DHCP lease + DNS name "vm-01" in mgmt-1 (live, no restart)
  - network: p2p-1
    ip: 192.168.1.1/24
  - bridge: br0           # host bridge instead of libvirt network
    target: vm01-p3       # host-side interface name (default vnetN)
    model: e1000          # virtio (default), e1000, e1000e, rtl8139
  - udp: 127.0.0.1:10002  # UDP tunnel to another VM's NIC, no bridge
    local: 127.0.0.1:10001
```

cloud-init installs `qemu-guest-agent`: clean shutdown and `virsh domifaddr <vm> --source agent`.

Jsonnet keeps repeated devices short (`topology/test.jsonnet/`):

```jsonnet
(import 'linux.libsonnet').linux(2)   // vm-02, IPs .2
```

## Usage

```shell
# define networks, then devices (not started)
uv run vlab -v deploy -n topology/test.yaml/mgmt-1.yaml -d topology/test.yaml/vm-1.yaml

# start / stop by device, VM name or --all
# stop = clean shutdown, power off after --timeout (60s); --force = power off right away
uv run vlab -v start --all
uv run vlab -v stop -d vm-01

# show VMs / VNets (running in green)
uv run vlab list vms
uv run vlab list vnets

# delete VMs; VM files removed unless --keep-files
uv run vlab -v delete -d vm-01
```

`-v` info, `-vv` debug (incl. generated XML). `deploy --overwrite` rebuilds existing VM files.

## Tests

```shell
uv run pytest
```

Tests use libvirt's in-memory `test:///default` driver and temp folders — the host's libvirt is not touched.
