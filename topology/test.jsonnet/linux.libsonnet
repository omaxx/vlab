// Linux server srv-<n> on mgmt-1 + LAN srv-<n> towards vmx-<n>
{
  srv(n):: {
    type: 'linux',
    name: 'srv-%d' % n,
    id: n,
    user: '$USER',
    ssh_key_files: ['~/.ssh/id_ed25519.pub', '~/.ssh/authorized_keys'],
    ports: [
      { network: 'mgmt-1', ip: '172.255.1.%d/24' % n, gateway: '172.255.1.254', dns: ['172.255.1.254'], dhcp: true },
      { p2p: 'srv-%d' % n, ip: '10.%d.0.10/24' % n, routes: { ['10.%d.0.0/24' % (3 - n)]: '10.%d.0.1' % n } },
    ],
  },
}
