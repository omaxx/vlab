{
  srv(n):: { name: 'srv-%d' % n, devices: ['srv-%d' % n, 'vmx-%d' % n] },
  p2p(n):: { name: 'p2p-%d' % n, devices: ['vmx-1', 'vmx-2'] },
}
