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

`topology/test.yaml/networks/mgmt.yaml` — NAT network, host IP = VM gateway/DNS:

```yaml
name: mgmt-1
ip: 172.255.1.254/24
forward: nat
# mtu: 9000              # optional, default 1500
# dhcp:                  # optional ranges / fixed hosts; devices add their own (port dhcp: true)
#   ranges: [{start: 172.255.1.100, end: 172.255.1.199}]
```

`forward: bridge` + `bridge: br0` wraps an existing host bridge as a network (no ip/dhcp/mtu).

Linux cloud image VM (image in `/var/lib/vlab/images/linux/`), configured by cloud-init:

```yaml
type: linux               # device type, required
name: srv-1
id: 1                     # MACs ca:ff:ee:01:00:<port>, host ifnames srv-1-<port>
user: $USER
ssh_key_files:
  - ~/.ssh/id_ed25519.pub
ports:                    # each: network | bridge | p2p | udp
  - network: mgmt-1       # existing libvirt network (not checked)
    ip: 172.255.1.1/24
    gateway: 172.255.1.254
    dns: [172.255.1.254]
    dhcp: true            # fixed DHCP lease + DNS name "srv-1" in mgmt-1 (live, no restart)
  - p2p: srv-1            # link network: created by first device, shared, removed with last device
    ip: 10.1.0.10/24
  - bridge: br0           # existing host bridge (not checked)
    target: srv-1-p3      # host-side interface name (default <device>-<N>)
    model: e1000          # virtio (default), e1000, e1000e, rtl8139
  - udp: 127.0.0.1:10002  # UDP tunnel to another VM's NIC, no bridge
    local: 127.0.0.1:10001
```

cloud-init installs `qemu-guest-agent`: clean shutdown and `virsh domifaddr <vm> --source agent`.

A topology file puts devices and networks together, keyed by name
(`topology/test.yaml/topology.yaml`: `[srv-1] -- srv-1 -- [vmx-1] -- p2p-1/p2p-2 -- [vmx-2] -- srv-2 -- [srv-2]`):

```yaml
devices:
  srv-1:                  # name from key
    type: linux
    ...
  vmx-1:
    type: jnpr/vmx        # Juniper vMX (RE + FPC VMs); also jnpr/vqfx
    config: vmx.conf.j2   # Jinja2 template in configs/, rendered with vars
    vars: {...}
    ports:
      - p2p: srv-1        # same p2p name on two devices = link between them
networks: {}              # regular networks (like networks/mgmt.yaml)
```

`vlab list vnets` kind: `device` (p2p / device-internal, with its devices), `network` (regular), `-` (created outside vlab, never touched).

Jsonnet keeps repeated devices short (`topology/test.jsonnet/`):

```jsonnet
(import 'linux.libsonnet').srv(2)   // srv-2, IPs .2
```

## Usage

```shell
# define networks, then devices (not started); -t topology, -n network, -d device (repeatable)
uv run vlab -v deploy -n topology/test.yaml/networks/mgmt.yaml -t topology/test.yaml/topology.yaml

# start / stop by device, VM name or --all
# stop = clean shutdown, power off after --timeout (60s); --force = power off right away
uv run vlab -v start --all
uv run vlab -v stop -d vmx-1

# show VMs / VNets (running in green)
uv run vlab list vms
uv run vlab list vnets

# delete VMs; VM files removed unless --keep-files
uv run vlab -v delete -d srv-1
```

`-v` info, `-vv` debug (incl. generated XML). `deploy --overwrite` rebuilds existing VM files.

## Tests

```shell
uv run pytest
```

Tests use libvirt's in-memory `test:///default` driver and temp folders — the host's libvirt is not touched.
