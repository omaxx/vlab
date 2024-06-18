local devices = (import "topology.jsonnet").devices;
local jnpr = import "../jnpr.jsonnet";
local vsrx_options = {
    images: "junos/vsrx",
    image: "junos-media-vsrx-x86-64-vmdisk-22.4R2-S2.6.qcow2",
};
local vsrx3_options = {
    images: "junos/vsrx3",
    image: "junos-vsrx3-x86-64-23.2R1-S2.5.qcow2",
};
{
    devices: [
        jnpr.vsrx({id: 1, name: "srx1", interfaces: devices[self.name].interfaces} + vsrx_options),
        jnpr.vsrx({id: 2, name: "srx2", interfaces: devices[self.name].interfaces} + vsrx_options),
    ],
}
