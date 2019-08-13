PARAMS = {
    "app_folder": "../",                 # Path where the glossy_test.c file is
    "sims_dir": "./simulations",         # Path where to store simulations in

    # list of nodes available
    # "nodes" : [1, 2, 3, 4 ,5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
    "nodes" : [1, 2, 3, 4 ,5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],

    # list describing, in each simulation, the node to be the initiator.
    # There will be a **separate** simulation for each of these nodes.
    "initiator": [3, 15],

    "payloads" : [0, 109],
    "powers"   : [0xd5],                # Default tx power for xx2538

    # If a time is given in format %Y-%m-%d %H:%M
    # then the first simulation is scheduled at that time
    # and all consecutive simulations will be scheduled
    # after an offset equals to the test duration
    # Time to schedule the simulation.
    "ts_init"  : "asap",

    "duration" : 600                    # Duration of each simulation
}
