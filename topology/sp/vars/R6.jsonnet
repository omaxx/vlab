// R6 template vars (configs/vmx.conf.j2)
(import 'common.libsonnet') + {
  interfaces: {
    "fxp0": { ip: "172.255.1.6/24" },
    "lo0": { ip: "10.0.0.6/32", ipv6: "fd00::6/128", iso: "49.0001.0100.0000.0006.00" },
    "ge-0/0/0": { description: "-> R2 : ge-0/0/2", ip: "10.0.26.6/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/1": { description: "-> R1 : ge-0/0/3", ip: "10.0.16.6/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/2": { description: "-> R5 : ge-0/0/2", ip: "10.0.56.6/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/3": { description: "-> R10 : ge-0/0/1", ip: "10.0.69.6/24" },
    "ge-0/0/4": { description: "-> R8 : ge-0/0/4", ip: "10.0.68.6/24", ipv6: true, iso: true, mpls: true },
  },
}
