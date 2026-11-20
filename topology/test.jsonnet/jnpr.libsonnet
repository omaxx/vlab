// vMX vmx-<n>: ge-0/0/0 p2p-1, ge-0/0/1 p2p-2 to the other vMX, ge-0/0/2 LAN srv-<n>
local ids = { '1': 3, '2': 5 };
{
  vmx(n):: {
    local id = ids[std.toString(n)],
    local peer = ids[std.toString(3 - n)],
    type: 'jnpr/vmx',
    name: 'vmx-%d' % n,
    id: id,
    version: '24.4R1-S2.9',
    re_image: 'junos-vmx-x86-64-24.4R1-S2.9.qcow2',
    fpc_image: 'vFPC-20241118.img',
    mgmt: { network: 'mgmt-1', ip: '172.255.1.%d/24' % id, dhcp: true },
    ports: [{ p2p: 'p2p-1' }, { p2p: 'p2p-2' }, { p2p: 'srv-%d' % n }],
    config: 'vmx.conf.j2',  // configs/vmx.conf.j2
    vars: {
      root_password: '$6$vlabvlab$5dQUFdNoOCf9So8AVoZ6h0YNmeTTcxbnITrhfaOBSO99pynAJEjKpJ28VT/7YgsVTfAbezIj2GwQjEF.gAD3m.',  // lab only: "vlab123"
      mgmt_address: '172.255.1.%d/24' % id,
      interfaces: {
        'ge-0/0/0': { address: '192.168.1.%d/24' % id },
        'ge-0/0/1': { address: '192.168.2.%d/24' % id },
        'ge-0/0/2': { address: '10.%d.0.1/24' % n },
      },
      static_routes: { ['10.%d.0.0/24' % (3 - n)]: '192.168.1.%d' % peer },
    },
  },
}
