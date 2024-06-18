local devices = (import "topology.jsonnet").devices;
local jnpr = import "../jnpr.jsonnet";
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
        jnpr.vmx({id: 1, name: "bb1", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 2, name: "bb2", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 3, name: "r11", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 4, name: "r12", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 5, name: "r21", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 6, name: "r22", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vqfx({id: 7, name: "sw11", interfaces: devices[self.name].interfaces} + vqfx_options),
        jnpr.vqfx({id: 8, name: "sw12", interfaces: devices[self.name].interfaces} + vqfx_options),
        jnpr.vqfx({id: 9, name: "sw21", interfaces: devices[self.name].interfaces} + vqfx_options),
        jnpr.vqfx({id: 10, name: "sw22", interfaces: devices[self.name].interfaces} + vqfx_options),
        jnpr.vmx({id: 11, name: "t", interfaces: devices[self.name].interfaces} + vmx_options),
    ],
}
