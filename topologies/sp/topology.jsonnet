{
    devices: {
        r1: {
            interfaces: {
                "ge-0/0/0": {network: "R1_R9"},
                "ge-0/0/1": {network: "R1_R2"},
                "ge-0/0/2": {network: "R1_R3"},
                "ge-0/0/3": {network: "R1_R4"},
            },
        },
        r2: {
            interfaces: {
                "ge-0/0/0": {network: "R1_R2"},
                "ge-0/0/1": {network: "R2_R3"},
                "ge-0/0/2": {network: "R2_R8"},
                "ge-0/0/3": {network: "R2_R5"},
            },
        },
        r3: {
            interfaces: {
                "ge-0/0/0": {network: "R2_R3"},
                "ge-0/0/1": {network: "R3_R4"},
                "ge-0/0/2": {network: "R3_R7"},
                "ge-0/0/3": {network: "R3_R7"},
            },
        },
        r4: {
            interfaces: {
                "ge-0/0/0": {network: "R3_R4"},
                "ge-0/0/1": {network: "R4_R5"},
                "ge-0/0/2": {network: "R1_R4"},
                "ge-0/0/3": {network: "R4_R6"},
            },
        },
        r5: {
            interfaces: {
                "ge-0/0/0": {network: "R4_R5"},
                "ge-0/0/1": {network: "R5_R6"},
                "ge-0/0/2": {network: "R2_R5"},
                "ge-0/0/3": {network: "R5_R8"},
            },
        },
        r6: {
            interfaces: {
                "ge-0/0/0": {network: "R5_R6"},
                "ge-0/0/1": {network: "R6_R7"},
                "ge-0/0/2": {network: "R4_R6"},
                "ge-0/0/3": {network: "R6_R9"},
            },
        },
        r7: {
            interfaces: {
                "ge-0/0/0": {network: "R6_R7"},
                "ge-0/0/1": {network: "R7_R8"},
                "ge-0/0/2": {network: "R7_R9"},
                "ge-0/0/3": {network: "R3_R7"},
            },
        },
        r8: {
            interfaces: {
                "ge-0/0/0": {network: "R7_R8"},
                "ge-0/0/1": {network: "R8_R9"},
                "ge-0/0/2": {network: "R5_R8"},
                "ge-0/0/3": {network: "R2_R8"},
            },
        },
        r9: {
            interfaces: {
                "ge-0/0/0": {network: "R8_R9"},
                "ge-0/0/1": {network: "R1_R9"},
                "ge-0/0/2": {network: "R6_R9"},
                "ge-0/0/3": {network: "R7_R9"},
            },
        },
    }
}