// R3 template vars (configs/vmx.conf.j2)
(import 'common.libsonnet') + {
  interfaces: {
    "fxp0": { ip: "172.255.1.3/24" },
    "lo0": { ip: "10.0.0.3/32", ipv6: "fd00::3/128", iso: "49.0002.0100.0000.0003.00" },
    "ge-0/0/0": { description: "-> R1 : ge-0/0/0", ip: "10.0.13.3/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/1": { description: "-> R2 : ge-0/0/1", ip: "10.0.23.3/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/2": { description: "-> R4 : ge-0/0/2", ip: "10.0.34.3/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/3": { description: "-> R7 : ge-0/0/0", ip: "10.0.37.3/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/4": { description: "-> R8 : ge-0/0/1", ip: "10.0.38.3/24", ipv6: true, iso: true, mpls: true },
  },
}
