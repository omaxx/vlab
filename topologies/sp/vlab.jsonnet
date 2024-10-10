local devices = (import "topology.jsonnet").devices;
local device(name) = {
    name: name,
} + devices[name];
local jnpr = (import "../vlab.libsonnet").jnpr;

local vmx_23_2R2_S1 = {
    images: "junos/vmx/23.2R2-S1.3/images",
    re_image: "junos-vmx-x86-64-23.2R2-S1.3.qcow2",
    fpc_image: "vFPC-20240508.img",
};
local vmx_20_4R3_S10 = {
    images: "junos/vmx/20.4R3-S10.2/images",
    re_image: "junos-vmx-x86-64-20.4R3-S10.2.qcow2",
    fpc_image: "vFPC-20220727.img",
};

{
    devices: [
        jnpr.vmx(1, device("BB11") + vmx_23_2R2_S1),
        jnpr.vmx(2, device("BB12") + vmx_23_2R2_S1),
        jnpr.vmx(3, device("BB21") + vmx_23_2R2_S1),
        jnpr.vmx(4, device("BB22") + vmx_23_2R2_S1),
        jnpr.vmx(5, device("PE11") + vmx_23_2R2_S1),
        jnpr.vmx(6, device("PE12") + vmx_23_2R2_S1),
        jnpr.vmx(7, device("PE21") + vmx_23_2R2_S1),
        jnpr.vmx(8, device("PE22") + vmx_23_2R2_S1),
        jnpr.vmx(9, device("CE") + vmx_23_2R2_S1),
    ]
}
