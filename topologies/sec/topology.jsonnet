{
    devices: {
        "srx1": {
            interfaces: {
                "ge-0/0/0": {bridge: "vmbr0"},
                "ge-0/0/1": {bridge: "vmbr1"},
            },
        },
        "srx2": {
            interfaces: {
                "ge-0/0/0": {bridge: "vmbr0"},
                "ge-0/0/1": {bridge: "vmbr2"},
            },
        },
    }
}