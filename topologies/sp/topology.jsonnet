{
    devices: {
        BB11: {
            interfaces: {
                "ge-0/0/0": {network: "BB11_BB21"},
                "ge-0/0/1": {network: "BB11_BB22"},
                "ge-0/0/2": {network: "BB11_PE11"},
                "ge-0/0/3": {network: "BB11_PE12"},
                "ge-0/0/4": {network: "BB11_BB12"},
            },
        },
        BB12: {
            interfaces: {
                "ge-0/0/0": {network: "BB12_BB22"},
                "ge-0/0/1": {network: "BB12_BB21"},
                "ge-0/0/2": {network: "BB12_PE12"},
                "ge-0/0/3": {network: "BB12_PE11"},
                "ge-0/0/4": {network: "BB11_BB12"},
            },
        },
        BB21: {
            interfaces: {
                "ge-0/0/0": {network: "BB11_BB21"},
                "ge-0/0/1": {network: "BB12_BB21"},
                "ge-0/0/2": {network: "BB21_PE21"},
                "ge-0/0/3": {network: "BB21_PE22"},
                "ge-0/0/4": {network: "BB21_BB22"},
            },
        },
        BB22: {
            interfaces: {
                "ge-0/0/0": {network: "BB12_BB22"},
                "ge-0/0/1": {network: "BB11_BB22"},
                "ge-0/0/2": {network: "BB22_PE22"},
                "ge-0/0/3": {network: "BB22_PE21"},
                "ge-0/0/4": {network: "BB21_BB22"},
            },
        },
        PE11: {
            interfaces: {
                "ge-0/0/0": {network: "BB11_PE11"},
                "ge-0/0/1": {network: "BB12_PE11"},
                "ge-0/0/2": {network: "PE11_PE12"},
                "ge-0/0/3": {network: "PE11_CE"},
                "ge-0/0/4": {network: "PE11_PE21"},
            },
        },
        PE12: {
            interfaces: {
                "ge-0/0/0": {network: "BB12_PE12"},
                "ge-0/0/1": {network: "BB11_PE12"},
                "ge-0/0/2": {network: "PE11_PE12"},
                "ge-0/0/3": {network: "PE12_CE"},
                "ge-0/0/4": {network: "PE12_PE22"},
            },
        },
        PE21: {
            interfaces: {
                "ge-0/0/0": {network: "BB21_PE21"},
                "ge-0/0/1": {network: "BB22_PE21"},
                "ge-0/0/2": {network: "PE21_PE22"},
                "ge-0/0/3": {network: "PE21_CE"},
                "ge-0/0/4": {network: "PE11_PE21"},
            },
        },
        PE22: {
            interfaces: {
                "ge-0/0/0": {network: "BB22_PE22"},
                "ge-0/0/1": {network: "BB21_PE22"},
                "ge-0/0/2": {network: "PE21_PE22"},
                "ge-0/0/3": {network: "PE22_CE"},
                "ge-0/0/4": {network: "PE12_PE22"},
            },
        },
        CE: {
            interfaces: {
                "ge-0/0/0": {network: "PE11_CE"},
                "ge-0/0/1": {network: "PE12_CE"},
                "ge-0/0/2": {network: "PE21_CE"},
                "ge-0/0/3": {network: "PE22_CE"},
                "ge-0/0/4": {bridge: "vmbr1"},
                "ge-0/0/5": {bridge: "vmbr2"},
            },
        },
    }
}
