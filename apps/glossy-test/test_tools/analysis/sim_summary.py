#!/usr/bin/python3
"""Module to collect few representative information
from simulation.
"""
import logging
import os
import csv

import re
import shutil

import matplotlib

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from matplotlib.backends.backend_pdf import PdfPages

from collections import OrderedDict
from pathlib import Path
from functools import reduce

from parser import get_log_data
from chart_config import init_matplotlib

from data_analysis import DAException
from data_analysis import clean_data
from data_analysis import get_sim_pdr, get_sim_first_relay_counter, get_sim_slot_estimation, get_sim_failed_slot_estimation
from data_analysis import get_sim_epoch_estimates
from data_analysis import get_sim_sync_counters
from data_analysis import get_sim_trx, get_sim_flood_trx
from data_analysis import get_sim_trx_errors, get_sim_trx_error_details, get_sim_pkt

from build_setting import SIM_CHANNEL
from build_setting import SIM_TXPOWER, SIM_INITIATOR, SIM_FRAMESIZE, SIM_NTX
from build_setting import SETTINGS_HEADER
from build_setting import parse_build_setting, get_settings_row

from navigator import simulation_log_iter, simulation_folder_iter_by_settings
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
logging.getLogger(__name__).setLevel(level=logging.DEBUG)

# higher the criticality for matplotlib logs (so to log **less**)
mpl_logger = logging.getLogger(matplotlib.__name__)
mpl_logger.setLevel(logging.WARNING)
# -----------------------------------------------------------------------------
init_matplotlib()

SUMMARY_STATS = "summary.csv"
PERNODE_STATS = "pernode.csv"
PKT_LOST_STATS = "pkt_lost.txt"
BUILD_SETTINGS= "build_settings.txt"
STATS_FOLDER  = "stats"
# -----------------------------------------------------------------------------
# CSV headers
# -----------------------------------------------------------------------------
NODE     = "node"
PDR      = "pdr"

# First relay counter statistics
FRC_AVG = "frc_avg"
FRC_MAX = "frc_max"
FRC_MIN = "frc_min"
FRC_PERCENTILE_25 = "frc_25th"
FRC_PERCENTILE_75 = "frc_75th"

SEQNO    = "seqno"
TSLOT_US = "t_slot_us"
PKT_SENT = "pkt_sent"
PKT_RCVD = "pkt_rcvd"
FLOOD_N_TX = "flood_n_tx"
FLOOD_N_RX = "flood_n_rx"

# summary fields
PDR_MEAN      = "pdr_mean"
PDR_MIN      = "pdr_min"
PDR_MAX      = "pdr_max"
# FRC_AVG -> avg of pernode frc average
FRC_MMAX = "frc_max" # max of frc max
FRC_MMIN = "frc_min" # min of frc min
FRC_MIN_P25 = "frc25_min" # min of frc 25th
FRC_MAX_P75 = "frc75_max" # max of frc 75th


ENERGY_HEADER      = [NODE, FLOOD_N_TX, FLOOD_N_RX, TSLOT_US]
PERFORMANCE_HEADER = ["num_nodes", PDR_MEAN, PDR_MIN, PDR_MAX, FRC_AVG, FRC_MMIN, FRC_MMAX, FRC_MIN_P25, FRC_MAX_P75, TSLOT_US, PKT_SENT, PKT_RCVD]
SUMMARY_HEADERS    = SETTINGS_HEADER + PERFORMANCE_HEADER
PERNODE_HEADER     = [NODE, PDR, FRC_AVG, FRC_MIN, FRC_MAX, FRC_PERCENTILE_25, FRC_PERCENTILE_75, TSLOT_US, PKT_RCVD]

# -----------------------------------------------------------------------------
# CHART CONFIGURATION KEYS
# -----------------------------------------------------------------------------
XLABEL = "xlabel"
YLABEL = "ylabel"
TITLE  = "title"
LEGEND = "legend"

def get_lost_pkt_table(nodes, lost_pkt):
    lost_set = reduce(set().union, map(set, lost_pkt.values()))

    nodes_pktloss = {p:{n:None for n in nodes} for p in sorted(lost_set)}
    for nid, nr in lost_pkt.items():
        for pkt in nr:
            nodes_pktloss[pkt][nid] = nid
    index = sorted(nodes_pktloss.keys())
    values = [[nodes_pktloss[i][node] for node in nodes] for i in index]

    rows = [[index[i]] + values[i] for i in range(0, len(index))]
    if len(rows) == 0:
        rows = [[None] * (len(nodes) + 1)]
    df = pd.DataFrame(rows, columns = [SEQNO] + nodes)
    df.fillna(value=pd.np.nan, inplace=True)
    return df

def get_simulation_summary(sim_name, sim_log_path, dest_folder=None):
    if dest_folder is None:
        dest_folder = os.path.dirname(sim_log_path)
    dest_folder = os.path.join(dest_folder, STATS_FOLDER)

    if os.path.exists(dest_folder) and os.path.isdir(dest_folder):
        logger.info("Stats directory {} already exists. Skipping computation...".format(dest_folder))
        return

    os.mkdir(dest_folder)
    # retrieve build settings configurations
    simdir = os.path.dirname(os.path.abspath(os.path.join(sim_log_path, "..")))
    settings_filename = os.path.join(simdir, BUILD_SETTINGS)

    pkt_size = 0
    try:
        settings = parse_build_setting(settings_filename)
        settings_values = get_settings_row(settings)
        pkt_size = settings[SIM_FRAMESIZE]
    except FileNotFoundError:
        logger.warning("%s not found in log folder. The summary will have missing fields" % BUILD_SETTINGS)
        logger.warning("Unknown packet size, set to 0...")
        settings_values = [None for i in SETTINGS_HEADER]

    try:
        print("-"*40 + "\nProcessing file:\n%s\n" % sim_log_path + "-"*40)
        log_data = get_log_data(sim_log_path)
        clean_data(log_data, 20)

        pkt_tx, nodes_rcvd, not_received = get_sim_pkt(log_data)
        nodes_pdr = {n: rx/pkt_tx for n, rx in nodes_rcvd.items()}
        nodes_frelay = get_sim_first_relay_counter(log_data)
        # collect estimates and convert them into microseconds
        # (1 ~= 4ns -> estimate * 4 / 1000)
        nodes_estimates = {n: [v * 31 / 1000 for v in estimates] for n, estimates in get_sim_slot_estimation(log_data).items()}
        nodes_tx, nodes_rx = get_sim_flood_trx(log_data)

        # keep an ordered list of nodes
        nodes = list(map(str, sorted(map(int, nodes_pdr.keys()))))

        perc_interpolation = "lower"
        pernode_rows = [[
            node,                                           # NODE
            nodes_pdr[node],                                # PDR
            # pick just the first mode
            np.mean(nodes_frelay[node]),                    # FRC_AVG
            np.min(nodes_frelay[node]),                     # FRC_MIN
            np.max(nodes_frelay[node]),                     # FRC_MAX
            np.percentile(nodes_frelay[node], 25, interpolation=perc_interpolation),      # FRC 25 PERC
            np.percentile(nodes_frelay[node], 75, interpolation=perc_interpolation),      # FRC 75 PERC
            np.average(nodes_estimates[node]),              # T_SLOT
            nodes_rcvd[node]                                # PKT_RCVD
            ] for node in nodes]

        pernode_df = pd.DataFrame(pernode_rows, columns=PERNODE_HEADER)

        summary_row = settings_values +\
            [len(nodes_pdr.keys()),\
            pernode_df[PDR].mean(),\
            pernode_df[PDR].min(),\
            pernode_df[PDR].max(),\
            pernode_df[FRC_AVG].mean(),\
            pernode_df[FRC_MIN].min(),\
            pernode_df[FRC_MAX].max(),\
            pernode_df[FRC_PERCENTILE_25].min(),\
            pernode_df[FRC_PERCENTILE_75].max(),\
            pernode_df[TSLOT_US].mean(),\
            pkt_tx,\
            pernode_df[PKT_RCVD].mean()]

        summary_df = pd.DataFrame([summary_row], columns=SUMMARY_HEADERS)
        lost_df = get_lost_pkt_table(nodes, not_received)

        pernode_filename = os.path.join(dest_folder, PERNODE_STATS)
        summary_filename = os.path.join(dest_folder, SUMMARY_STATS)
        pkt_lost_filename = os.path.join(dest_folder, PKT_LOST_STATS)
        with open(pernode_filename, "w") as pernode_fh,\
             open(summary_filename, "w") as summary_fh,\
             open(pkt_lost_filename,"w") as lost_fh:

            lost_fh.write(lost_df.fillna("NA").to_string(index=False))
            pernode_fh.write(pernode_df.to_csv(index=False))
            summary_fh.write(summary_df.to_csv(index=False))

    except DAException as e:
        raise e

    except BaseException as e:
        shutil.rmtree(dest_folder)
        raise e

# -----------------------------------------------------------------------------
# MAIN-SCRIPT FUNCTIONS
# -----------------------------------------------------------------------------
def producer_main(args):
    if os.path.isfile(args.log_source):

        log_reg = re.compile(r"(?:.*/)*(.*).log$")
        match = log_reg.match(args.log_source)
        if match:
            name = match.group(1)
            get_simulation_summary(name, args.log_source, dest_folder=None)
        else:
            raise ValueError("The file given is not a log file")

    elif os.path.isdir(args.log_source):

        sim_done = 0
        sim_undone = []
        for sim_name, log_path in simulation_log_iter(args.log_source):
            try:
                get_simulation_summary(sim_name, log_path, dest_folder=None)
                sim_done += 1
            except DAException as e:
                # data analysis exceptions are important, don't skip them
                raise e
            except Exception as e:
                logger.error("Invalid log found. Skipped: {}".format(log_path))
                raise e
                sim_undone.append(log_path)

        print("-"*40)
        print("{} simulations successfully processed".format(sim_done))
        print("{} simulations haven't been processed due to errors".format(len(sim_undone)))
        print("-"*40)

        if len(sim_undone) > 0:
            print("Bad logs:\n" + "-"*40)
        for badlog in sim_undone:
            print(badlog)

def get_x_field(df, x_ref, x_column, field_column):
    """Given a reference list of x values (total number of values
    to plot on x axis), create a list of y values of the same
    length.

    If a y value is not found for a given x, insert None
    to its place. This makes y values aligned to a global x axis,
    accounting also for missing data.
    """
    aligned_result = OrderedDict((x_val,None) for x_val in x_ref)
    x_found   = df[x_column].to_list()
    val_found = df[field_column].to_list()

    x_val_found = OrderedDict((x_found[i], val_found[i]) for i in range(0, len(x_found)))
    # you have found more values than expected, something
    # is not as intended, throw an error!
    if len(aligned_result) != len(x_val_found):
        raise ValueError("Shape of values found is different from the given x-axis reference length")

    for x,val in x_val_found.items():
        aligned_result[x] = val
    return aligned_result

POWER_SETTINGS = [SIM_CHANNEL, SIM_TXPOWER]
def get_pdr_n(df):
    """Group simulations based on radio configuration. Aggregate
    pdr values of simulations with same glossy version and same
    packet size and n.

    Return pdr values for both glossy versions as function on the
    reliability parameter N, for each packet size and radio configuration.
    """
    pdr_df = df.groupby(POWER_SETTINGS + [PACKET_SIZE, SIM_NTX], as_index=False).agg({PDR:"mean"})
    pdr_df.sort_values(SIM_NTX, inplace=True)

    pkt_sizes = pdr_df[PACKET_SIZE].unique().tolist()
    reliability = sorted(pdr_df[SIM_NTX].unique().tolist())

    data = {}
    for pwsettings, pw_df in pdr_df.groupby(POWER_SETTINGS):

        data[pwsettings] = {}
        # produce a separate plot for each pkt size
        for pkt_size in sorted(pkt_sizes):

            df = pdr_df[(pw_df[SIM_FRAMESIZE] == pkt_size)]
            pdr_val = list(get_x_field(df, reliability, SIM_NTX, PDR).values())

            data[pwsettings][pkt_size] = pdr_val

    return reliability, data


def get_field_per_n(fixed_init_df, field):
    fixed_df = fixed_init_df.copy()
    fixed_df.sort_values(SIM_NTX, inplace=True)

    # exclude repeated experiments
    fixed_df.drop_duplicates(POWER_SETTINGS + [SIM_NTX, SIM_FRAMESIZE, NODE], inplace=True)

    # apparently, pandas read node ids as integers rather than strings
    nodes      = sorted(fixed_df[NODE].unique().tolist())
    reliability= sorted(fixed_df[SIM_NTX].unique().tolist())

    data = []
    for pwsettings, pw_df in fixed_df.groupby(SIM_POWER_SETTINGS, as_index=False):
        for pkt_size,size_df in pw_df.groupby(SIM_FRAMESIZE, as_index=False):

            ntx_values = OrderedDict(((r, None) for r in reliability))
            for ntx in reliability:

                tmp = size_df[(size_df[SIM_NTX] == ntx)]
                tmp = tmp.sort_values(NODE)
                ntx_values[ntx] = get_x_field(tmp, nodes, NODE, field)

            data.append((pwsettings, pkt_size, ntx_values))
    return nodes, reliability, data

def replace_with(x, cond, with_):
    if cond(x):
        return with_
    return x

def plot_pdr_n(reliability, pdr_data):
    # use these values to compute axis dimensions
    x = reliability
    # collect of y values from all configurations
    y = []
    for settings in pdr_data.values():
        for pdr_val in settings.values():
            y.extend(list(filter(None, pdr_val)))

    std = np.std(y)
    ylim_max = max(y) + std
    ylim_min = min(y) - std

    for settings, pkt_sizes in pdr_data.items():
        for pkt_size, pdr in pkt_sizes.items():

            # replace None values with 0
            replace_none = lambda x: replace_with(x, lambda y: y is None, with_=0)
            pdr_val = list(map(replace_none, pdr))

            plt.figure()
            ind = np.arange(len(x))
            b1 = plt.bar(ind, pdr, width=width)
            plt.ylim([ylim_min, ylim_max])
            #plt.xticks(ind + width / 2, x)
            plt.xlabel("N")
            plt.ylabel("PDR")

            title = "Small packets"
            if pkt_size > min(pkt_sizes):
                title = "Big packets"

            plt.title(title)
            #plt.legend((b1[0], b2[0]), ("Standard", "Tx-Only"))

            plt.show()

def set_default_chart_params(params):
    full_params = {XLABEL:None, YLABEL:None, TITLE:None, LEGEND: None}
    for k,v in params.items():
        full_params[k] = v
    return full_params

def plot_field_node(nodes, levels, field_data, chart_params):
    chart_params = set_default_chart_params(chart_params)

    x = nodes
    # replace None values with 0
    replace_none = lambda x: replace_with(x, lambda y: y is None, with_=0)
    pkt_sizes = [pkt_size for _, pkt_size,_ in field_data]
    for settings, pkt_size, ntx_data in field_data:

        bars = []
        numbar = 0
        ind = np.arange(len(x))
        width  = 1 / (len(ntx_data) + 1)
        for ntx, nodes_field in ntx_data.items():

            node_values = list(nodes_field.values())
            y = list(map(replace_none, node_values))
            b = plt.bar(ind + (width * numbar), y, width=width)
            numbar += 1
            bars.append(b)

        plt.xticks(ind + width, x)
        plt.xlabel(chart_params[XLABEL])
        plt.ylabel(chart_params[YLABEL])

        pkt_title = "Small packets"
        if pkt_size > min(pkt_sizes):
            pkt_title = "Big packets"

        title = str.join(" ", filter(None, [chart_params[TITLE], str.join(", ", map(str, list(settings))), pkt_title]))

        plt.title(title)
        plt.legend(tuple(bars), tuple(levels))

        plt.show()



if __name__ == "__main__":
    import argparse
    import sys

    BASE_PATH = os.path.dirname(sys.argv[0])
    APP_SOURCE= os.path.abspath(os.path.join(BASE_PATH, "..", "..", "glossy_test.c"))

    # -------------------------------------------------------------------------
    # PARSING ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers(dest="command")
    parser.set_defaults(func=lambda x: parser.print_help())

    # STATS PRODUCER PARSER
    producer_parser = subparser.add_parser("produce", help="produce stats files")
    producer_parser.add_argument("log_source",\
            help="The log file to analyse or the folder from which start searching logs")
    producer_parser.set_defaults(func=producer_main)

    # COLLECTOR
    collector_parser = subparser.add_parser("collect", help="collect summary files")
    collector_parser.add_argument("start_folder",\
            help="The folder from which start searching for summary files")
    collector_parser.set_defaults(func=parser.print_help)

    args = parser.parse_args()
    out = args.func(args)

