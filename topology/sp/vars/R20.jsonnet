// R20 template vars (configs/vmx.conf.j2)
(import 'common.libsonnet') + {
  interfaces: {
    "fxp0": { ip: "172.255.1.20/24" },
    "lo0": { ip: "10.0.0.20/32" },
    "ge-0/0/0": { description: "-> R7 : ge-0/0/3", ip: "10.0.79.9/24" },
    "ge-0/0/1": { description: "-> R8 : ge-0/0/3", ip: "10.0.89.9/24" },
    "ge-0/0/2": { description: "-> CE-20", ip: "192.168.20.254/24" },
  },
}
