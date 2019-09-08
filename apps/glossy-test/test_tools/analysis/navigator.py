#!/usr/bin/python3
import os
import re
import logging

import pandas as pd
from pathlib import Path

from build_setting import parse_build_setting, get_sim_name, get_sim_name_abbrev

# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
logging.getLogger(__name__).setLevel(level=logging.DEBUG)
# -----------------------------------------------------------------------------

BUILD_SETTINGS="build_settings.txt"
SETTINGS = "settings.csv"

def simulation_log_iter(str_start_path):
    """Iterate over all folders starting from the
    application directory, considering any folder containing
    a .log file.

    Return all individual simulation folders.
    A pair <name, path> is returned for each simulation
    """
    logger.info("Searching log files starting from: {}".format(str_start_path))
    log_paths = Path(str_start_path).glob("**/*.log")

    log_reg = re.compile(r"(?:.*/)*(.*).log$")
    for log_path in log_paths:
        log_folder = os.path.dirname(os.path.abspath(str(log_path)))
        simdir = os.path.join(log_folder, "..")

        settings_file  = os.path.join(simdir, SETTINGS)
        if not (os.path.exists(settings_file) and os.path.isfile(settings_file)):
            continue

        settings = pd.read_csv(settings_file)
        settings = {k:v[0] for k,v in settings.to_dict(orient="list").items()}
        confname = get_sim_name_abbrev(settings)

        match = log_reg.match(str(log_path))
        if match:
            name = match.group(1) + "_" + confname
            yield name, str(log_path)


def simulation_folder_iter_by_settings(str_start_path, condition_dict={}):
    """Return every simulation folder looking at the corresponding
    settings file. Optionally only folders matching
    a given build settings criteria can be returned."""
    logger.info("Searching build_setting files starting from: {}".format(str_start_path))
    settings_paths = Path(str_start_path).glob("**/%s" % SETTINGS)

    for settings_path in settings_paths:
        settings = pd.read_csv(str(settings_path))
        settings = {k:v[0] for k,v in settings.to_dict(orient="list").items()}

        to_yield = True
        for field, value in condition_dict.items():
            if settings[field] != value:
                to_yield = False
                break
        if to_yield is True:
            yield os.path.dirname(os.path.abspath(str(settings_path)))




