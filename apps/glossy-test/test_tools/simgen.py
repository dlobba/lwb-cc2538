#!/usr/bin/env python3
import os
import sys
BASE_PATH = os.path.dirname(sys.argv[0])
sys.path.insert(0, os.path.join(BASE_PATH, "analysis"))

import re
import json
import copy
import datetime

import itertools
import subprocess
import git        # pick last commit hash
import pandas as pd
import shutil
from random import randint
from collections import OrderedDict

from jinja2 import Template

import build_setting
from params import PARAMS
from simgen_templates import TESTBED_TEMPLATE


PRJ_NTX = "ntx"
PRJ_TX_POWER = "tx_power"
PRJ_PAYLOAD = "payload"
PRJ_INITIATOR = "initiator"

# -----------------------------------------------------------------------------
# Extract parameters from from the params.py to generate simulations

ALL_NODES = set(PARAMS["nodes"])
INITS     = set(PARAMS["initiator"])
SIM_DURATION = int(PARAMS["duration"])
TS_INIT   = PARAMS["ts_init"]
PAYLOADS  = PARAMS["payloads"]
NTXS  = PARAMS["ntxs"]
POWERS   = PARAMS["powers"]

SIMULATION_OFFSET = 60                  # Time used to separate two consecutive simulations

# -----------------------------------------------------------------------------
# Compute paths to required files and directories

BASE_PATH = os.path.dirname(sys.argv[0])
APP_DIR   = os.path.join(os.path.abspath(BASE_PATH), PARAMS["app_folder"])
APP_BINARY= os.path.abspath(os.path.join(APP_DIR, "glossy_test.bin"))
APP_SOURCE= os.path.abspath(os.path.join(APP_DIR, "glossy_test.c"))
APP_PRJCONF = os.path.abspath(os.path.join(APP_DIR, "project-conf.h"))
SIMS_DIR  = os.path.abspath(os.path.join(BASE_PATH, PARAMS["sims_dir"]))

# -----------------------------------------------------------------------------
# SINGLE SIMULATION VARIABLES
# -----------------------------------------------------------------------------
TESTBED_FILENAME   = "glossy_test_simulation.json"
BINARY_FILENAME    = "glossy_test_simulation.bin"
PROJECT_CONF       = "project_conf.h"
BUILD_SETTINGS     = "build_settings.txt"
BUILD_OUT          = "build_out.txt"
# -----------------------------------------------------------------------------
TESTBED_INIT_TIME_FORMAT = "%Y-%m-%d %H:%M"


def check_params():
    """Check on params.

    * every initiator is an available node
    * the application folder contains effectively glossy_test.c
    * the application folder contains the app binary glossy_test.bin
    * check if simulations directory **can** be created (creation occurs later on)
    * duration is an integer number
    * payloads are within the range
    """
    if len(INITS) < 1:
        raise ValueError("No initiator node defined")
    if not INITS.issubset(ALL_NODES):
        raise ValueError("Initiators are not a subset of nodes available")

    application_path = os.path.join(APP_DIR, "glossy_test.c")
    if not os.path.exists(application_path):
        raise ValueError("The given app folder doesn't contain glossy_test.c\n" +
            "Given: {}".format(application_path))

    # check the simulations dir is not a normal file (wtf?!)
    if os.path.exists(SIMS_DIR) and os.path.isfile(SIMS_DIR):
        raise ValueError("Cannot create simulations directory. A file with the same name already exists.")

    if len(PAYLOADS) < 1:
        raise ValueError("No payload defined")
    for payload in PAYLOADS:
        if payload < 0 or payload > 117:
            raise ValueError("Defined payload size is not within the boundary 0-117, given {}".format(payload))
    if len(NTXS) < 1:
        raise ValueError("No NTX defined")
    for ntx in NTXS:
        try:
            if ntx < 0 or ntx > 16:
                raise ValueError("Defined ntx value is not within the range 0-16, given {}".format(ntx))
        except TypeError:
            raise ValueError("NTXS must be a list of integers")


    for power in POWERS:
        if power < -24 or power > 7:
            raise ValueError("invalid power value given, allowed range " +
                    "[-24, +7] given {}".format(power))
    return True

def get_project_cflags(flag_values):
    """Define the additional cflags to set project macros.
    It is assumed the makefile not to add the value if empty.
    The variables here refer to those defined in the project Makefile.
    """
    defines = [
        "INITIATOR_ID=%d"     % flag_values[PRJ_INITIATOR],
        "PAYLOAD_LEN=%d"      % flag_values[PRJ_PAYLOAD],
        "TX_POWER=%s"         % flag_values[PRJ_TX_POWER],
        "NTX=%s"              % flag_values[PRJ_NTX]
    ]
    return defines

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
    period, slot, guard = tuple( ("NA " * 3).split() )

    with open(APP_SOURCE, "r") as fh:
        for line in fh:
            period_match = period_reg.match(line.lower())
            slot_match   = slot_reg.match(line.lower())
            guard_match  = guard_reg.match(line.lower())

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

    # period, slot and guard should be greater than 0
    if not all(map(lambda x: x and x > 0, (period, slot, guard))):
        raise ValueError("Some parameters in the glossy_test.c are not defined " +\
                "or are their value is below 1ms granularity."+\
                " In the latter case, change the reference granualarity in simgen.py")

    return period, slot, guard

def generate_simulations(overwrite=False):
    """Create a simulation folder for each configuration

    * the simulation has a name made by:

        a. from glossy_test.c
            1. epoch
            2. slot
            3. guard time
            4. number of transmission

        b. payload length
        c. duration of the simulaton
        d. initiator id

        The simulation name will be used in the simulation folder creation
        and to determine the path used to store results later

    * producing the binary
    * copying the project conf file
    * creating a json file to use in the unitn testbed
    """
    testbed_template   = Template(TESTBED_TEMPLATE)

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
    PERIOD, SLOT, GUARD = list(get_glossy_test_conf())
    NAME_PREFIX = "period%d_slot%d_guard%d" % (PERIOD, SLOT, GUARD)

    simulations = 0
    for init_id, ntx, txpower, payload in itertools.product(INITS,\
                                       NTXS,
                                       POWERS,
                                       PAYLOADS):
        json_sim = copy.deepcopy(json_testbed)

        # give a name to current simulation and create
        # the corresponding folder
        sim_name = NAME_PREFIX + "_ntx{}_txpower{}_payload{}_duration{}_init{}"\
                .format(ntx, re.sub("-", "m", str(txpower)), payload, SIM_DURATION, init_id)
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

        try:
            os.mkdir(sim_dir)

            # abs path for testbed file
            sim_testbed_file  = os.path.join(sim_dir, TESTBED_FILENAME)

            # copy binary and the project conf and get related abs paths
            abs_sim_binary = os.path.abspath(os.path.join(sim_dir, BINARY_FILENAME))
            abs_sim_prconf = os.path.abspath(os.path.join(sim_dir, PROJECT_CONF))
            abs_build_settings  = os.path.abspath(os.path.join(sim_dir, BUILD_SETTINGS))
            abs_build_out  = os.path.abspath(os.path.join(sim_dir, BUILD_OUT))
            abs_sim_settings = os.path.abspath(os.path.join(sim_dir, build_setting.SIM_SETTINGS))
            current_dir = os.getcwd()
            os.chdir(APP_DIR)
            print("-"*40 + "\nCleaning previous build")
            subprocess.check_call(["make","clean"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

            print("-"*40 + "\nBuilding simulation\n" + "-" * 40)
            # save configuration settings printed at compile time (through pragmas)
            # to the simulation directory.
            #
            # If compilation went wrong, print all the output to stdout
            pragmas = []
            outlines  = []
            pragma_message = re.compile(".*note:\s+#pragma message:\s+(.*)")
            # compute argument string for configuration parameters
            # They will be passed to make
            arg_conf = get_project_cflags({
                PRJ_NTX:       ntx,
                PRJ_INITIATOR: init_id,
                PRJ_PAYLOAD:   payload,
                PRJ_TX_POWER:  txpower
                })
            make_process = subprocess.Popen(["make"] + arg_conf, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
            for line in make_process.stdout:
                line = line.decode("utf-8")
                match = pragma_message.match(line)
                if match:
                    pragmas.append(match.group(1))
                outlines.append(line)
            make_process.wait()

            if make_process.returncode != 0:
                print(str.join("", outlines))
                raise subprocess.CalledProcessError(returncode=make_process.returncode, cmd="make")
            else:
                # print to stdout the pragmas as feedback
                print(str.join("\n", pragmas))


            bsettings = build_setting.parse_build_setting_lines(pragmas)
            channel = build_setting.get_radio_channel(bsettings)
            sim_conf=build_setting.get_settings_summary(bsettings)

            # save settings to the corresponding csv
            values = list(sim_conf.values())
            columns= list(sim_conf.keys())
            simconf_sf = pd.DataFrame([values], columns=columns)
            simconf_sf.to_csv(abs_sim_settings, index=False)
            # save build settings to simdir
            with open(abs_build_settings, "w") as fh:
                fh.write(str.join("\n", pragmas) + "\n")
            # save build output
            with open(abs_build_out, "w") as fh:
                fh.write(str.join("", outlines) + "\n")

            # return to previous directory
            os.chdir(current_dir)

            shutil.copy(APP_BINARY, abs_sim_binary)
            shutil.copy(APP_PRJCONF, abs_sim_prconf)

            # fill templates with simulation particulars
            json_sim["image"]["file"] = abs_sim_binary
            json_sim["image"]["target"] = list(ALL_NODES)
            # include the last commit of the repo in the json file.
            # Still, the user has to commit any new change in order
            # for this info to be useful at all
            json_sim["commit_id"] = str(git.Repo(APP_DIR, search_parent_directories=True).head.commit)

            # if scheduling has to be planned, then add to each
            # simulation an offset equal to the test duration
            if plan_schedule:
                json_sim["ts_init"] = datetime.datetime\
                        .strftime(sim_ts_init, TESTBED_INIT_TIME_FORMAT)
                sim_ts_init += datetime.timedelta(seconds=SIM_DURATION + SIMULATION_OFFSET)

            # convert json back to string
            sim_testbed = json.dumps(json_sim, indent=1)

            with open(sim_testbed_file, "w") as fh:
                fh.write(sim_testbed)

        except BaseException as e:
            clean_simgen_temp()
            # delete current simulation directory
            shutil.rmtree(sim_dir)
            raise e

        # increse sim counter
        simulations += 1

    # try to clean the project
    try:
        clean_simgen_temp()
    except:
        pass

    print("{} Simulations generated\n".format(simulations) + "-"*40)

def clean_simgen_temp():
    print("-"*40 + "\nCleaning simgen temporary files...\n" + "-"*40)
    current_dir = os.getcwd()
    os.chdir(APP_DIR)
    subprocess.check_call(["make","clean"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    os.chdir(current_dir)

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

