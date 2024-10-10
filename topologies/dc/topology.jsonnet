{
    devices: {
        BB1: {
            interfaces: {
                "ge-0/0/0": {network: "BB1_BB2_1"},
                "ge-0/0/1": {network: "BB1_BB2_2"},
                "ge-0/0/2": {network: "BB1_R11"},
                "ge-0/0/3": {network: "BB1_R12"},
                "ge-0/0/4": {network: "BB1_R21"},
                "ge-0/0/5": {network: "BB1_R22"},
            },
        },
        BB2: {
            interfaces: {
                "ge-0/0/0": {network: "BB1_BB2_1"},
                "ge-0/0/1": {network: "BB1_BB2_2"},
                "ge-0/0/2": {network: "BB2_R11"},
                "ge-0/0/3": {network: "BB2_R12"},
                "ge-0/0/4": {network: "BB2_R21"},
                "ge-0/0/5": {network: "BB2_R22"},
            },
        },
        R11: {
            interfaces: {
                "ge-0/0/0": {network: "BB1_R11"},
                "ge-0/0/1": {network: "BB2_R11"},
                "ge-0/0/2": {network: "R11_SW11"},
                "ge-0/0/3": {network: "R11_SW12"},
            },
        },
        R12: {
            interfaces: {
                "ge-0/0/0": {network: "BB1_R12"},
                "ge-0/0/1": {network: "BB2_R12"},
                "ge-0/0/2": {network: "R12_SW11"},
                "ge-0/0/3": {network: "R12_SW12"},
            },
        },
        R21: {
            interfaces: {
                "ge-0/0/0": {network: "BB1_R21"},
                "ge-0/0/1": {network: "BB2_R21"},
                "ge-0/0/2": {network: "R21_SW21"},
                "ge-0/0/3": {network: "R21_SW22"},
            },
        },
        R22: {
            interfaces: {
                "ge-0/0/0": {network: "BB1_R22"},
                "ge-0/0/1": {network: "BB2_R22"},
                "ge-0/0/2": {network: "R22_SW21"},
                "ge-0/0/3": {network: "R22_SW22"},
            },
        },
        SW11: {
            interfaces: {
                "ge-0/0/0": {network: "R11_SW11"},
                "ge-0/0/1": {network: "R12_SW11"},
                "ge-0/0/2": {network: "T_SW11_1"},
                "ge-0/0/3": {network: "T_SW11_2"},
            },
        },
        SW12: {
            interfaces: {
                "ge-0/0/0": {network: "R11_SW12"},
                "ge-0/0/1": {network: "R12_SW12"},
                "ge-0/0/2": {network: "T_SW12_1"},
                "ge-0/0/3": {network: "T_SW12_2"},
            },
        },
        SW21: {
            interfaces: {
                "ge-0/0/0": {network: "R21_SW21"},
                "ge-0/0/1": {network: "R22_SW21"},
                "ge-0/0/2": {network: "T_SW21_1"},
                "ge-0/0/3": {network: "T_SW21_2"},
            },
        },
        SW22: {
            interfaces: {
                "ge-0/0/0": {network: "R21_SW22"},
                "ge-0/0/1": {network: "R22_SW22"},
                "ge-0/0/2": {network: "T_SW22_1"},
                "ge-0/0/3": {network: "T_SW22_2"},
            },
        },
        T: {
            interfaces: {
                "ge-0/0/0": {network: "T_SW11_1"},
                "ge-0/0/1": {network: "T_SW11_2"},
                "ge-0/0/2": {network: "T_SW12_1"},
                "ge-0/0/3": {network: "T_SW12_2"},
                "ge-0/0/4": {network: "T_SW21_1"},
                "ge-0/0/5": {network: "T_SW21_2"},
                "ge-0/0/6": {network: "T_SW22_1"},
                "ge-0/0/7": {network: "T_SW22_2"},
            },
        },
    }
}