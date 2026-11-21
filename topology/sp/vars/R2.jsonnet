// R2 template vars (configs/vmx.conf.j2)
(import 'common.libsonnet') + {
  interfaces: {
    "fxp0": { ip: "172.255.1.2/24" },
    "lo0": { ip: "10.0.0.2/32", ipv6: "fd00::2/128", iso: "49.0001.0100.0000.0002.00" },
    "ge-0/0/0": { description: "-> R4 : ge-0/0/0", ip: "10.0.24.2/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/1": { description: "-> R3 : ge-0/0/1", ip: "10.0.23.2/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/2": { description: "-> R1 : ge-0/0/2", ip: "10.0.12.2/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/3": { description: "-> R6 : ge-0/0/0", ip: "10.0.26.2/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/4": { description: "-> R5 : ge-0/0/1", ip: "10.0.25.2/24", ipv6: true, iso: true, mpls: true },
  },
}
