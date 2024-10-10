local devices = (import "topology.jsonnet").devices;
local device(name) = {
    name: name,
} + devices[name];
local jnpr = (import "../vlab.libsonnet").jnpr;

local vmx_23_2R2_S1 = {
    images: "junos/vmx/23.2R2-S1.3/images",
    re_image: "junos-vmx-x86-64-23.2R2-S1.3.qcow2",
    fpc_image: "vFPC-20240508.img",
    re_num: 2,
    fpc_num: 2,
};
local vmx_20_4R3_S10 = {
    images: "junos/vmx/20.4R3-S10.2/images",
    re_image: "junos-vmx-x86-64-20.4R3-S10.2.qcow2",
    fpc_image: "vFPC-20220727.img",
    re_num: 2,
    fpc_num: 2,
};
local vmx_18_4R3_S11 = {
    images: "junos/vmx/18.4R3-S11/images",
    re_image: "junos-vmx-x86-64-18.4R3-S11.qcow2",
    fpc_image: "vFPC-20201215.img",
    re_num: 2,
    fpc_num: 2,
};
local vmx_16_2R2_S11 = {
    images: "junos/vmx/16.2R2-S11/images",
    re_image: "junos-vmx-x86-64-16.2R2-S11.qcow2",
    fpc_image: "vFPC-20180920.img",
    re_num: 2,
    fpc_num: 2,
};

{
    devices: [
        jnpr.vmx(1, device("R1") + vmx_23_2R2_S1),
        jnpr.vmx(2, device("R2") + vmx_20_4R3_S10),
    ]
}
