// Debian VM on mgmt-1 (NAT) + p2p-1 + p2p-2, IPs end with id
{
  debian(id):: {
    name: 'vm-%02d' % id,
    id: id,
    user: '$USER',
    ssh_key_files: ['~/.ssh/id_ed25519.pub', '~/.ssh/authorized_keys'],
    ports: [
      { network: 'mgmt-1', ip: '172.255.1.%d/24' % id, gateway: '172.255.1.254', dns: ['172.255.1.254'], dhcp: true },
      { network: 'p2p-1', ip: '192.168.1.%d/24' % id },
      { network: 'p2p-2', ip: '192.168.2.%d/24' % id },
    ],
  },
}
