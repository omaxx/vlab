// R8 template vars (configs/vmx.conf.j2)
(import 'common.libsonnet') + {
  interfaces: {
    "fxp0": { ip: "172.255.1.8/24" },
    "lo0": { ip: "10.0.0.8/32", ipv6: "fd00::8/128", iso: "49.0002.0100.0000.0008.00" },
    "ge-0/0/0": { description: "-> R4 : ge-0/0/2", ip: "10.0.48.8/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/1": { description: "-> R3 : ge-0/0/3", ip: "10.0.38.8/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/2": { description: "-> R7 : ge-0/0/2", ip: "10.0.78.8/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/3": { description: "-> R20 : ge-0/0/1", ip: "10.0.89.8/24" },
    "ge-0/0/4": { description: "-> R6 : ge-0/0/4", ip: "10.0.68.8/24", ipv6: true, iso: true, mpls: true },
  },
}
