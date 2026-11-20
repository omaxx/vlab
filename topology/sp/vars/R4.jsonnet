// R4 template vars (configs/vmx.conf.j2)
(import 'common.libsonnet') + {
  interfaces: {
    "fxp0": { ip: "172.255.1.4/24" },
    "lo0": { ip: "10.0.0.4/32", ipv6: "fd00::4/128", iso: "49.0002.0100.0000.0004.00" },
    "ge-0/0/0": { description: "-> R2 : ge-0/0/0", ip: "10.0.24.4/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/1": { description: "-> R1 : ge-0/0/1", ip: "10.0.14.4/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/2": { description: "-> R8 : ge-0/0/0", ip: "10.0.48.4/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/3": { description: "-> R7 : ge-0/0/1", ip: "10.0.47.4/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/4": { description: "-> R3 : ge-0/0/4", ip: "10.0.34.4/24", ipv6: true, iso: true, mpls: true },
  },
}
