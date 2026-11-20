// R5 template vars (configs/vmx.conf.j2)
(import 'common.libsonnet') + {
  interfaces: {
    "fxp0": { ip: "172.255.1.5/24" },
    "lo0": { ip: "10.0.0.5/32", ipv6: "fd00::5/128", iso: "49.0001.0100.0000.0005.00" },
    "ge-0/0/0": { description: "-> R1 : ge-0/0/2", ip: "10.0.15.5/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/1": { description: "-> R2 : ge-0/0/3", ip: "10.0.25.5/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/2": { description: "-> R6 : ge-0/0/2", ip: "10.0.56.5/24", ipv6: true, iso: true, mpls: true },
    "ge-0/0/3": { description: "-> R10 : ge-0/0/0", ip: "10.0.59.5/24" },
    "ge-0/0/4": { description: "-> R7 : ge-0/0/4", ip: "10.0.57.5/24", ipv6: true, iso: true, mpls: true },
  },
}
