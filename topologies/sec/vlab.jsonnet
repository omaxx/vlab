local devices = (import "topology.jsonnet").devices;
local device(name) = {
    name: name,
} + devices[name];
local jnpr = (import "../vlab.libsonnet").jnpr;

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
        jnpr.vsrx(1, device("srx1") + vsrx_options),
        jnpr.vsrx(2, device("srx2") + vsrx_options),
    ]
}
