local devices = (import "topology.jsonnet").devices;
local jnpr = import "../jnpr.jsonnet";
local vmx_options = {
    images: "junos/vmx/23.2R2/images",
    re_image: "junos-vmx-x86-64-23.2R2.21.qcow2",
    fpc_image: "vFPC-20240301.img",
};
{
    devices: [
        jnpr.vmx({id: 1, name: "r1", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 2, name: "r2", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 3, name: "r3", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 4, name: "r4", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 5, name: "r5", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 6, name: "r6", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 7, name: "r7", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 8, name: "r8", interfaces: devices[self.name].interfaces} + vmx_options),
        jnpr.vmx({id: 9, name: "r9", interfaces: devices[self.name].interfaces} + vmx_options),
    ],
}
