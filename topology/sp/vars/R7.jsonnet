// R7 template vars (configs/vmx.conf.j2)
(import 'common.libsonnet') + {
  interfaces: {
    "fxp0": { ip: "172.255.1.7/24" },
    "lo0": { ip: "10.0.0.7/32", ipv6: "fd00::7/128", iso: "49.0002.0100.0000.0007.00" },
    "ge-0/0/0": { description: "-> R3 : ge-0/0/2", ip: "10.0.37.7/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/1": { description: "-> R4 : ge-0/0/3", ip: "10.0.47.7/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/2": { description: "-> R8 : ge-0/0/2", ip: "10.0.78.7/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/3": { description: "-> R20 : ge-0/0/0", ip: "10.0.79.7/24" },
    "ge-0/0/4": { description: "-> R5 : ge-0/0/4", ip: "10.0.57.7/24", ipv6: true, iso: true, mpls: true },
  },
}
