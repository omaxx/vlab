// R10 template vars (configs/vmx.conf.j2)
(import 'common.libsonnet') + {
  interfaces: {
    "fxp0": { ip: "172.255.1.10/24" },
    "lo0": { ip: "10.10.0.1/32" },
    "ge-0/0/0": { description: "-> R5 : ge-0/0/3", ip: "10.0.59.9/24" },
    "ge-0/0/1": { description: "-> R6 : ge-0/0/3", ip: "10.0.69.9/24" },
  },
}
