local RE_CONSOLE_PORT = 8600;
local FPC_CONSOLE_PORT = 9600;

local vmx(id, arg) = {
    local device = {
        re_num: 1,
        re_vcpu: 1,
        re_memory: 1024,
        fpc_num: 1,
        fpc_vcpu: 3,
        fpc_memory: 2048,
    } + arg,
    name: device.name,
    interfaces: device.interfaces,
    vms: [
        {
            local vm = self,
            name: device.name + "~re" + slot,
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
                {bridge: "mgmt", target: vm.name + "~mgmt", mac: "C0:FF:EE:" + id + ":" + (10 + slot) + ":00"}, 
                {network: device.name + "~int", target: vm.name + "~int"},
            ],
            console: RE_CONSOLE_PORT + id + 100 * slot,
        } for slot in std.range(0, device.re_num - 1)
    ] + [
        {
            local vm = self,
            name: device.name + "~fpc" + slot,
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
                {bridge: "mgmt", target: vm.name + "~mgmt", mac: "C0:FF:EE:" + id + ":" + (slot) + ":ff"}, 
                {network: device.name + "~int", target: vm.name + "~int"},
            ] + [
                interface.value + {
                    target: vm.name + "~" + std.substr(interface.key, 7, 2), 
                    mac: "C0:FF:EE:" + id + ":" + (slot) + ":" + std.substr(interface.key, 7, 2),
                }
                for interface in std.objectKeysValues(device.interfaces) 
                if std.substr(interface.key, 0, 4) == "ge-" + slot
            ],
            console: FPC_CONSOLE_PORT + id + 100 * slot,
        } for slot in std.range(0, device.fpc_num - 1)
    ],
    vnets: [
        {name: device.name + "~int"},
    ]
};

local vqfx(id, arg) = {
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

local vsrx(id, arg) = {
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
    jnpr: {
        vmx: vmx,
        vqfx: vqfx,
        vsrx: vsrx,
    },
}
