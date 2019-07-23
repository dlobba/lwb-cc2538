PARAMS = {
    "app_folder": "../",                  # Path where the glossy_test.c file is
    "sims_dir": "../simulations2",         # Path where to store simulations in

    # list of nodes available
    "nodes" : [11, 12, 10, 13, 14, 15, 16, 17, 2, 1, 4, 5],

    # list describing, in each simulation, the node to be the initiator.
    # There will be a **separate** simulation for each of these nodes.
    "initiator": [11, 12, 10, 13, 14, 15, 16, 17, 2, 1, 4, 5],


    # If a time is given in format %Y-%m-%d %H:%M
    # then the first simulation is scheduled at that time
    # and all consecutive simulations will be scheduled
    # after an offset equals to the test duration
    # Time to schedule the simulation.
    "ts_init"  : "asap",

    "duration" : 600                       # Duration of each simulation
}
