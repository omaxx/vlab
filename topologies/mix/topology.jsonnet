{
    devices: {
        R1: {
            interfaces: {
                "ge-0/0/0": {network: "R1_R2_1"},
                "ge-0/0/1": {network: "R1_R2_2"},
                "ge-1/0/0": {network: "R1_R2_3"},
                "ge-1/0/1": {network: "R1_R2_4"},
            }
        },
        R2: {
            interfaces: {
                "ge-0/0/0": {network: "R1_R2_1"},
                "ge-0/0/1": {network: "R1_R2_2"},
                "ge-1/0/0": {network: "R1_R2_3"},
                "ge-1/0/1": {network: "R1_R2_4"},
            }
        },
    }
}