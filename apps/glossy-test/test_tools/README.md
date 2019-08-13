# `simgen.py` - Plan simulations with less pain!

Simgen is program which automates simulations management.
It does so by:

* generating single folder where simulations are gathered,
* generating a folder for each simulation, named after configuration
  parameters related both to Glossy and Glossy-Test settings in addition
  to the id of the initiator. The folder contains:

  1. the copy of the binary file used;
  2. a copy of the `project-conf.h` file used by the simulation;
  3. a `glossy_test_sim.json` file, ready to be sent to the testbed, with
     **absolute paths** to the binary and the pfile required (present in the current
     simulation directory).

     The set of keys has been extended with a `sim_id` field, which contains
     an identifier to the current simulation (matching the simulation folder's name).

    The identifier for the commit repo has been added too.

**NOTE:**

* `simgen.py` deals with invalid scenarios by raising exceptions.
  These are thought to provide valuable insight on the possible errors
  occurring.

  *So be patient and read the last lines of the traceback.*
  *You won't regret it!*


## Simulations settings

Simgen produces simulations based on settings defined in the
`params.py` file.

```python
PARAMS = {
    "app_folder": "../",
    "sims_dir": "../simulations",

    # list of nodes available
    "nodes" : [11, 12, 10, 13, 14, 15, 16, 17, 2, 1, 4, 5],

    "initiator": [11, 12, 10, 13, 14, 15, 16, 17, 2, 1, 4, 5],

    "payloads" : [0, 109],
    "powers"   : [0xd5],        # default power setting

    "ts_init"  : "asap",

    "duration" : 60    # Duration of each simulation
}
```

Where:

* `app_folder` is the path where the `glossy_test.c`, `project-conf.h`
    and `glossy_test.bin` files are supposed to be found,

* `sims_dir` is the path used to store simulations produced,

* `nodes` defines the list of available tesbed nodes,

* `initiator` defines a list of nodes that will be, **within different
  simulations**, the initiators. At every simulation there will
  be a single initiator.

* `payloads` is a list containing payload values to be used in simulations
   packets. The accepted range 0 - 109

* `powers` is a list defining the transmission power settings to
  be used to generate configurations.

* `duration` defines the duration (in **seconds**) for a single
  simulation.

* `ts_init` defines the corresponding parameter for the testbed `.json`
  file, with just one extensions:

  in case it defines an actual schedule, in the format `%Y-%m-%d %H:%M`,
  then the first simulation is scheduled at that time and all
  consecutive simulations will be interleaved by an offset equals
  to the duration of a single simulation.


## Usage

By issuing the program `simgen.py` without any argument,
the directory, where simulations will be stored, is made
and a separate folder is made for each initiator defined in `params.py`.

A folder's name differs based on the following:

* it will contain a sequence of three timing values, expressed
  in *milliseconds* represing the *period*, the *slot* and
  the *guard time* used by Glossy-Test;

* it will contain a string `ntx<K>` where `K` defines the maximum number
  of transmissions (within a flood) defined in Glossy-Test;

* it will contain a string `txpower0x<V>` where `V` is the tx power value
  assigned.

* it will contain a string `payload<L>` where `L` is the length of the
  payload used as the application data.

* finally it will contain a string identifying the duration (in
  *seconds*) of the simulation and the id of the initiator.

For instance, one such string is:
`500ms_100ms_1ms_ntx2_txpower0xd5_payload109_duration60_init15`.


By default, during simulation's creation, the process will raise
an error and stops whenever a simulation folder with the same
name already exists.

To avoid this behaviour and forcing the generation process, it is
possible to issue `simgen.py` with the `--force-generation` flag on.
This makes the program **overwrite** the folder in case of name clashes,
**overwriting any possible content**.

To print the values defined in `params.py` and currently used
by simgen, issue the command `simgen.py -pi`.

To delete the main simulation folder and all its content (hence,
**every simulation**), issue the `simgen.py -d` command.
The program will ask the user to enter a randomly generated 5 cyphers
code and, upon correct insertion, will delete the main simulation
folder.

**Remember:** `simgen.py -h` is your friend!

## A practical use case

1. Tune `glossy_test.c` file to your liking.
2. Write to `test_tools/params.py` the duration of the simulations
   the `ts_init`, the set of testbed nodes to use and the set
   of testbed nodes to use as initiator.

3. Execute `simgen.py` (`-fg` if you are sure to overwrite possible
   folders already existing).

4. Browse each new simulation's folder and schedule the simulation
   to the testbed.
