#!/usr/bin/env python3
import os
import sys
import re
import json
import copy
import datetime

import shutil
from random import randint

from jinja2 import Template

from params import PARAMS
from simgen_templates import SERIALCOM_TEMPLATE, TESTBED_TEMPLATE


ALL_NODES = set(PARAMS["nodes"])
INITS     = set(PARAMS["initiator"])
SIM_DURATION = int(PARAMS["duration"])
TS_INIT   = PARAMS["ts_init"]

SIMULATION_OFFSET = 60                  # Time used to separate two consecutive simulations

BASE_PATH = os.path.dirname(sys.argv[0])
APP_DIR   = os.path.join(os.path.abspath(BASE_PATH), PARAMS["app_folder"])
APP_BINARY= os.path.abspath(os.path.join(APP_DIR, "glossy_test.bin"))
APP_SOURCE= os.path.abspath(os.path.join(APP_DIR, "glossy_test.c"))
SIMS_DIR  = os.path.abspath(os.path.join(BASE_PATH, PARAMS["sims_dir"]))

# -----------------------------------------------------------------------------
# SINGLE SIMULATION VARIABLES
# -----------------------------------------------------------------------------
SERIALCOM_FILENAME = "serialcom_init.py"
TESTBED_FILENAME   = "glossy_test_simulation.json"
BINARY_FILENAME    = "glossy_test_simulation.bin"
PROJECT_CONF       = "project_conf.h"

# -----------------------------------------------------------------------------
TESTBED_INIT_TIME_FORMAT = "%Y-%m-%d %H:%M"


def check_params():
    """Check on params.

    * every initiator is an available node
    * the application folder contains effectively glossy_test.c
    * the application folder contains the app binary glossy_test.bin
    * check if simulations directory **can** be created (creation occurs later on)
    * duration is an integer number
    """
    if not INITS.issubset(ALL_NODES):
        raise ValueError("Initiators are not a subset of nodes available")

    application_path = os.path.join(APP_DIR, "glossy_test.c")
    if not os.path.exists(application_path):
        raise ValueError("The given app folder doesn't contain glossy_test.c\n" +
            "Given: {}".format(application_path))

    if not os.path.exists(APP_BINARY):
        raise ValueError("The given app folder doesn't contain glossy_test.bin\n" +
            "Generate the binary first!")

    # check the simulations dir is not a normal file (wtf?!)
    if os.path.exists(SIMS_DIR) and os.path.isfile(SIMS_DIR):
        raise ValueError("Cannot create simulations directory. A file with the same name already exists.")

    return True

def get_glossy_test_conf():
    """Extract configuration define in the glossy_test.c file.
    """
    RTIMER_SYMBOLIC = r"rtimer_second"
    # assume millisecond granularity
    # if this is not sufficient (IT SHOULD BE!) throw an error an inform
    # the user that this code should be changed to the new granularity
    # by changing the value of RTIMER_VALUE

    RTIMER_VALUE = "1000"               # ms granularity
    GRANULARITY  = "ms"
    period_reg = re.compile(r"\s*#define\s+glossy_period\s+(\([^\)]*\))")
    slot_reg   = re.compile(r"\s*#define\s+glossy_t_slot\s+(\([^\)]*\))")
    guard_reg  = re.compile(r"\s*#define\s+glossy_t_guard\s+(\([^\)]*\))")
    ntx_reg    = re.compile(r"\s*#define\s+glossy_n_tx\s+(\d+)")
    period, slot, guard, ntx = tuple( ("NA " * 4).split() )

    with open(APP_SOURCE, "r") as fh:
        for line in fh:
            period_match = period_reg.match(line.lower())
            slot_match   = slot_reg.match(line.lower())
            guard_match  = guard_reg.match(line.lower())
            ntx_match    = ntx_reg.match(line.lower())


            if period_match:
                period = period_match.group(1)
                period = re.sub(RTIMER_SYMBOLIC, RTIMER_VALUE, period)
                period = int(eval(period))
            if slot_match:
                slot = slot_match.group(1)
                slot = re.sub(RTIMER_SYMBOLIC, RTIMER_VALUE, slot)
                slot = int(eval(slot))
            if guard_match:
                guard = guard_match.group(1)
                guard = re.sub(RTIMER_SYMBOLIC, RTIMER_VALUE, guard)
                guard = int(eval(guard))
            if ntx_match:
                ntx = int(ntx_match.group(1))

    # period, slot and guard should be greater than 0
    if not all(map(lambda x: x and x > 0, (period, slot, guard))):
        raise ValueError("Some parameters in the glossy_test.c are not defined " +\
                "or are their value is below 1ms granularity."+\
                " In the latter case, change the reference granualarity in simgen.py")

    time_params = [str(x) + GRANULARITY for x in (period, slot, guard)]
    params = time_params.copy()
    params.append("ntx{}".format(ntx))
    return tuple(params)

def generate_simulations(overwrite=False):
    """Create a simulation folder for each configuration

    * the simulation has a name made by:

        a. the glossy configuration
            1. version and
            2. estimation approach used

        a2. from glossy_test.c
            1. epoch
            2. slot
            3. guard time
            4. number of transmission

        b. duration of the simulation
        c. initiator id

        The simulation name will be used in the simulation folder creation
        and to determine the path used to store results later

    * copying the binary
    * copying the project conf file
    * creating a pFile to write the initiator id through serial
    * creating a json file to use in the unitn testbed
    * create a .txt file containing the filename used to give a meaningful name to the test
    """
    testbed_template   = Template(TESTBED_TEMPLATE)
    serialcom_template = Template(SERIALCOM_TEMPLATE)

    # create dir in which collecting simulations
    if not os.path.exists(SIMS_DIR):
        os.makedirs(SIMS_DIR)

    # Render the json test template with common values
    # In each simulation fill the differing details using
    # directly the json structure
    testbed_filled_template   = testbed_template.render(\
            duration_seconds = SIM_DURATION,\
            duration_minutes = int(SIM_DURATION / 60),\
            ts_init = TS_INIT)
    json_testbed  = json.loads(testbed_filled_template)

    # check if the json define a scheduled init
    plan_schedule = False
    try:
        sim_ts_init = datetime.datetime.\
                strptime(json_testbed["ts_init"], TESTBED_INIT_TIME_FORMAT)
        plan_schedule = True
    except ValueError:
        pass

    # get a prefix based on glossy configuration which are
    # common to all simulations currently generated
    prefix_items = list(get_glossy_test_conf())
    # DO NOT(!) change this from now on
    SIM_PREFIX   = str.join("_", prefix_items)

    for node_id in INITS:

        json_sim = copy.deepcopy(json_testbed)

        # give a name to current simulation and create
        # the corresponding folder
        sim_name = SIM_PREFIX + "_duration{}_init{}"\
                .format(SIM_DURATION, node_id)
        sim_dir  = os.path.join(SIMS_DIR, sim_name)

        # if a folder with the same name already existed then
        # check if overwrite is set
        # * if it is, then remove the previous directory and
        #   create a brand new dir
        # * if not, raise an exception
        if os.path.exists(sim_dir):
            if overwrite:
                shutil.rmtree(sim_dir)
            else:
                raise ValueError("A simulation folder with the same "+\
                        "name already exists: {}".format(sim_dir))

        os.mkdir(sim_dir)
        # get the absolute path to the pfile for the current
        # sim folder
        abs_sim_pfile = os.path.join(sim_dir, SERIALCOM_FILENAME)
        abs_sim_pfile = os.path.abspath(abs_sim_pfile)

        # abs path for testbed file
        sim_testbed_file  = os.path.join(sim_dir, TESTBED_FILENAME)

        # copy binary and the project conf and get related abs paths
        abs_sim_binary = os.path.abspath(os.path.join(sim_dir, BINARY_FILENAME))
        abs_sim_prconf = os.path.abspath(os.path.join(sim_dir, PROJECT_CONF))
        shutil.copy(APP_BINARY, abs_sim_binary)

        # fill templates with simulation particulars
        sim_serialcom = serialcom_template.render(init_id = node_id)
        json_sim["image"]["file"] = abs_sim_binary
        json_sim["python_script"] = abs_sim_pfile
        json_sim["image"]["target"] = list(ALL_NODES)
        json_sim["sim_id"] = sim_name

        # if scheduling has to be planned, then add to each
        # simulation an offset equal to the test duration
        if plan_schedule:
            json_sim["ts_init"] = datetime.datetime\
                    .strftime(sim_ts_init, TESTBED_INIT_TIME_FORMAT)
            sim_ts_init += datetime.timedelta(seconds=SIM_DURATION + SIMULATION_OFFSET)

        # convert json back to string
        sim_testbed = json.dumps(json_sim, indent=1)

        with open(abs_sim_pfile, "w") as fh:
            fh.write(sim_serialcom)
        with open(sim_testbed_file, "w") as fh:
            fh.write(sim_testbed)

def delete_simulations():
    if not os.path.exists(SIMS_DIR):
        raise ValueError("Simulations directory doesn't exist. Nothing done")
    # generate a random sequence of a given length
    code_len = 5
    code = ""
    for i in range(0, code_len):
        code += str(randint(0, 9))
    user_code = input("Write the following security code before " +
        "deletion to be performed: {}\n".format(code))
    if user_code.strip() == code:
        print("Removing dir {}".format(SIMS_DIR))
        shutil.rmtree(SIMS_DIR)
        print("DONE!")
    else:
        print("Wrong security code given. Abort deletion...")


if __name__ == "__main__":

    from argparse import ArgumentParser

    parser = ArgumentParser(description="Glossy SIMGEN. Manage simulations (hopefully) without pain!")
    parser.add_argument("-fg" ,"--force-generation", action="store_true", help="REMOVE(!) previous sim folder in case of name clashes")
    parser.add_argument("-ti" ,"--testbed-info", action="store_true", help="Return the testbed file used in generated simulations")
    parser.add_argument("-pi" ,"--params-info", action="store_true", help="Return parameters used in generated simulations")
    parser.add_argument("-d" ,"--delete-simulations", action="store_true", help="DELETE(!) the main simulation folder and all its contents")

    args = parser.parse_args()

    if args.testbed_info:
        print(TESTBED_TEMPLATE)
        sys.exit(0)
    elif args.params_info:
        import pprint
        pprint.pprint(PARAMS)
        sys.exit(0)
    if args.delete_simulations:
        delete_simulations()
        sys.exit(0)

    if not check_params():
        raise ValueError("Some parameter was not set correctly!")

    overwrite = False
    if args.force_generation:
        overwrite = True
    generate_simulations(overwrite)

