PARAMS = {
    "app_folder": "../",                 # Path where the glossy_test.c file is
    "sims_dir": "./",         # Path where to store simulations in

    # list of nodes available
    "nodes" : [],

    # list describing, in each simulation, the node to be the initiator.
    # There will be a **separate** simulation for each of these nodes.
    "initiator" : [],

    "ntxs"     : [2],
    "payloads" : [2],
    "powers"   : [-24, -15, -13, -11, -9, -7, -5, -3, -1, 0],                # Default tx power for cc2538

    # If a time is given in format %Y-%m-%d %H:%M
    # then the first simulation is scheduled at that time
    # and all consecutive simulations will be scheduled
    # after an offset equals to the test duration
    # Time to schedule the simulation.
    "ts_init"  : "asap",

    "duration" : 120                    # Duration of each simulation
}
