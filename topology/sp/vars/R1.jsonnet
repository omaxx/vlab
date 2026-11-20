// R1 template vars (configs/vmx.conf.j2)
(import 'common.libsonnet') + {
  interfaces: {
    "fxp0": { ip: "172.255.1.1/24" },
    "lo0": { ip: "10.0.0.1/32", ipv6: "fd00::1/128", iso: "49.0001.0100.0000.0001.00" },
    "ge-0/0/0": { description: "-> R3 : ge-0/0/0", ip: "10.0.13.1/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/1": { description: "-> R4 : ge-0/0/1", ip: "10.0.14.1/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/2": { description: "-> R5 : ge-0/0/0", ip: "10.0.15.1/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/3": { description: "-> R6 : ge-0/0/1", ip: "10.0.16.1/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/4": { description: "-> R2 : ge-0/0/4", ip: "10.0.12.1/24", ipv6: true, iso: true, mpls: true },
  },
}
