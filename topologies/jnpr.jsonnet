local vmx(arg) = {
    local device = {
        re_num: 1,
        re_vcpu: 1,
        re_memory: 1024,
        fpc_num: 1,
        fpc_vcpu: 3,
        fpc_memory: 2048,
    } + arg,
    name: device.name,
    vms: [
        {
            name: device.name + "~re" + slot,
            // device_id: device.id,
            // device_name: device.name,
            // slot: slot,
            xml: "jnpr-vmx-re",
            path: device.name + "/re" + slot,
            vcpu: device.re_vcpu,
            memory: device.re_memory,
            src: device.images,
            images: [
                {path: device.re_image}, 
                {path: "vmxhdd.img"}, 
                {path: "metadata-usb-re" + slot + ".img"},
            ],
            interfaces: [
                // {bridge: "mgmt"}, {network: device.name + "~int"}
            ],
        } for slot in std.range(0, device.re_num - 1)
    ] + [
        {
            name: device.name + "~fpc" + slot,
            // device_id: device.id,
            // device_name: device.name,
            // slot: slot,
            xml: "jnpr-vmx-fpc",
            path: device.name + "/fpc" + slot,
            vcpu: device.fpc_vcpu,
            memory: device.fpc_memory,
            src: device.images,
            images: [
                {path: device.fpc_image}, 
                {path: "metadata-usb-fpc" + slot + ".img"},
            ],
            interfaces: [
                // {bridge: "mgmt"}, {network: device.name + "~int"}
            ] + [
                interface.value 
                for interface in std.objectKeysValues(device.interfaces) 
                if std.substr(interface.key, 0, 4) == "ge-" + slot
            ],
        } for slot in std.range(0, device.fpc_num - 1)
    ],
    vnets: [
        {name: device.name + "~int"},
    ],
};
local vqfx(arg) = {
    local device = {
        re_num: 1,
        re_vcpu: 1,
        re_memory: 1024,
        fpc_num: 1,
        fpc_vcpu: 1,
        fpc_memory: 1024,
    } + arg,
    name: device.name,
    vms: [
        {
            name: device.name + "~re" + slot,
            // device_id: device.id,
            // device_name: device.name,
            // slot: slot,
            xml: "jnpr-vqfx-re",
            path: device.name + "/re" + slot,
            vcpu: device.re_vcpu,
            memory: device.re_memory,
            src: device.images,
            images: [device.re_image],
            interfaces: [{bridge: "mgmt"}, {network: device.name + "~int"}, {network: device.name + "~res"}] + [
                interface.value 
                for interface in std.objectKeysValues(device.interfaces) 
                if std.substr(interface.key, 0, 4) == "ge-" + slot
            ],
        } for slot in std.range(0, device.re_num - 1)
    ] + [
        {
            name: device.name + "~fpc" + slot,
            // device_id: device.id,
            // device_name: device.name,
            // slot: slot,
            xml: "jnpr-vqfx-fpc",
            path: device.name + "/fpc" + slot,
            vcpu: device.fpc_vcpu,
            memory: device.fpc_memory,
            src: device.images,
            images: [device.fpc_image],
            interfaces: [{bridge: "mgmt"}, {network: device.name + "~int"}, {network: device.name + "~res"}],
        } for slot in std.range(0, device.fpc_num - 1)
    ],
    vnets: [
        {name: device.name + "~int"},
        {name: device.name + "~res"},
    ],
};
local vsrx(arg) = {
    local device = {
        vcpu: 1,
        memory: 1024,
    } + arg,
    name: device.name,
    vms: [
        {
            name: device.name,
            xml: "jnpr-vsrx",
            path: device.name,
            vcpu: device.vcpu,
            memory: device.memory,
            src: device.images,
            images: [device.image],
            interfaces: [{bridge: "mgmt"}] + [
                interface.value 
                for interface in std.objectKeysValues(device.interfaces) 
                if std.substr(interface.key, 0, 4) == "ge-0"
            ],
        }
    ],
    vnets: [],
};
{
    vmx: vmx,
    vqfx: vqfx,
    vsrx: vsrx,
}