local devices = (import "topology.jsonnet").devices;
local device(name) = {
    name: name,
} + devices[name];
local jnpr = (import "../vlab.libsonnet").jnpr;

local vmx_options = {
    images: "junos/vmx/23.2R2/images",
    re_image: "junos-vmx-x86-64-23.2R2.21.qcow2",
    fpc_image: "vFPC-20240301.img",
};
local vqfx_options = {
    images: "junos/vqfx/20.2",
    re_image: "vqfx-20.2R1.10-re-qemu.qcow2",
    fpc_image: "vqfx-20.2R1-2019010209-pfe-qemu.qcow",
};

{
    devices: [
        jnpr.vmx(1, device("BB1") + vmx_options),
        jnpr.vmx(2, device("BB2") + vmx_options),
        jnpr.vmx(3, device("R11") + vmx_options),
        jnpr.vmx(4, device("R12") + vmx_options),
        jnpr.vmx(5, device("R21") + vmx_options),
        jnpr.vmx(6, device("R22") + vmx_options),
        jnpr.vqfx(7, device("SW11") + vqfx_options),
        jnpr.vqfx(8, device("SW12") + vqfx_options),
        jnpr.vqfx(9, device("SW21") + vqfx_options),
        jnpr.vqfx(10, device("SW22") + vqfx_options),
        jnpr.vmx(11, device("T") + vqfx_options),
    ]
}
