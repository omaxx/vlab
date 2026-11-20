local id = 3;
{
  type: 'jnpr/vmx',
  name: 'vmx-1',
  id: id,
  version: '24.4R1-S2.9',
  re_image: 'junos-vmx-x86-64-24.4R1-S2.9.qcow2',
  fpc_image: 'vFPC-20241118.img',
  mgmt: { network: 'mgmt-1', ip: '172.255.1.%d/24' % id, dhcp: true },
  ports: [{ network: 'p2p-1' }, { network: 'p2p-2' }],
  config: 'vmx.conf.j2',  // configs/vmx.conf.j2
  vars: {
    root_password: '$6$vlabvlab$5dQUFdNoOCf9So8AVoZ6h0YNmeTTcxbnITrhfaOBSO99pynAJEjKpJ28VT/7YgsVTfAbezIj2GwQjEF.gAD3m.',  // lab only: "vlab123"
    mgmt_address: '172.255.1.%d/24' % id,
    interfaces: [
      { name: 'ge-0/0/%d' % i, address: '192.168.%d.%d/24' % [i + 1, id] }
      for i in [0, 1]
    ],
  },
}
