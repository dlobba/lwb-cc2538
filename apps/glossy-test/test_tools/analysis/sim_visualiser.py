#!/usr/bin/python3
"""Module to plot data related to a single
simulation.
"""
import math
import logging
import os

import re
import shutil
import datetime

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

from matplotlib.backends.backend_pdf import PdfPages

from pathlib import Path

from parser import get_log_data

from data_analysis import clean_data
from data_analysis import get_sim_pdr, get_sim_first_relay_counter, get_sim_slot_estimation, get_sim_failed_slot_estimation
from data_analysis import get_sim_epoch_estimates
from data_analysis import get_sim_sync_counters
from data_analysis import get_sim_trx, get_sim_flood_trx
from data_analysis import get_sim_trx_errors, get_sim_trx_error_details, get_sim_pkt


matplotlib.style.use(["seaborn"])

rc_params = {
"lines.linewidth"   : 1.5,      # line width in points
"lines.antialiased" : True,     # render lines in antialiased (no jaggies)
"patch.linewidth"   : .5,       # edge width in points.
"patch.antialiased" : True,     # render patches in antialiased (no jaggies)
"patch.facecolor"   : "C1",
"boxplot.whiskers"  : 1.0,
"boxplot.patchartist" : True,
"boxplot.showfliers"  : True,
"boxplot.flierprops.linewidth" : .8,
"boxplot.boxprops.linewidth"   : .8,
"boxplot.whiskerprops.linewidth" : .8,
"boxplot.capprops.linewidth"     : .8,
"boxplot.medianprops.linewidth" : 1.0,
"boxplot.meanprops.linewidth"   : 1.0,
"boxplot.medianprops.color"     : "black",
"font.size"         : 11.0,
"axes.linewidth"    : 0.8,          # edge linewidth
"axes.titlesize"    : "large",      # fontsize of the axes title
"axes.titlepad"     : 6.0,          # pad between axes and title in points
"axes.labelpad"     : 6.0,          # space between label and axis
"axes.labelsize"    : "large",      # space between label and axis
"axes.grid"         : True,         # display grid or not
"xtick.major.width" : 0.8,          # major tick width in points
"xtick.minor.width" : 0.6,          # minor tick width in points
"xtick.labelsize"   : "medium",     # fontsize of the tick labels
"ytick.major.width" : 0.8,          # major tick width in points
"ytick.minor.width" : 0.6,          # minor tick width in points
"ytick.labelsize"   : "medium",     # fontsize of the tick labels
"grid.linewidth"    : 0.8,          # in points
"legend.loc"        : "best",
"legend.frameon"    : True,         # if True, draw the legend on a background patch
"legend.framealpha" : 0.9,          # legend patch transparency
"legend.fancybox"   : True,         # if True, use a rounded box for the
"legend.fontsize"   : "medium",
"image.cmap"        : "tab20"
}

for k,v in rc_params.items():
    matplotlib.rcParams[k] = v

# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
logging.getLogger(__name__).setLevel(level=logging.DEBUG)

# higher the criticality for matplotlib logs (so to log **less**)
mpl_logger = logging.getLogger(matplotlib.__name__)
mpl_logger.setLevel(logging.WARNING)
# -----------------------------------------------------------------------------

def plot_pdr(nodes_pdr):
    """
    Produce a barplot displaying the PDR for each
    node.
    """
    x = [int(node_id) for node_id in nodes_pdr.keys()]         # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    y = [nodes_pdr[nid] for nid in x]

    mean = sum(y) / len(y)
    std  = math.sqrt(sum([(yi - mean)**2 for yi in y]))/len(y)
    if std < 0.000000001:
        std = 0.001
        ylim_max = 1 + std * 0.05
        ylim_min = min(y) - std
    else:
        ylim_max = 1 + std
        ylim_min = min(y) - std
    plt.bar(x, y)
    plt.ylim([ylim_min, ylim_max])
    plt.axhline(y=1, xmin=0, xmax=1, c="C2")
    plt.xlabel("Nodes")
    plt.ylabel("PDR")

def plot_reception_summary(pkt_tx, nodes_rx):
    str_ = "Packets broadcast: {}\n\n".format(pkt_tx)
    for nid in sorted([int(i) for i in nodes_rx]):
        str_ += "Node {}: {}\n".format(str(nid).zfill(2),\
                nodes_rx[str(nid)])
    plt.axes([0.01, 0.01, 0.98, 0.90], facecolor="white", frameon=True)
    axis = plt.gca()
    axis.set_xlim(0., 1.)
    axis.set_ylim(0., 1.)
    axis.set_ylabel("Summary", visible=False)
    axis.set_xlabel("Nodes", visible=False)
    axis.set_xticklabels("", visible=False)
    axis.set_yticklabels("", visible=False)
    axis.grid(False)
    plt.annotate(str_, xy=(0.5, 0.2), ha="center", fontsize=12)
    plt.title("Summary:")

def plot_first_relay_counter(nodes_frelay):
    """Produce a box blot of the values
    assumed by the first relay counter during across
    the considered floods."""
    x = [int(nid) for nid in nodes_frelay.keys()]  # node ids
    x.sort()
    x = [str(nid) for nid in x]
    y = [nodes_frelay[nid] for nid in x]           # relay counters

    plt.boxplot(y, showfliers=True, autorange=True)
    locs, labels = plt.xticks()
    plt.xticks(locs, x)
    plt.xlabel("Nodes")
    plt.ylabel("First relay counter")
    return x,y

def plot_failed_slot_estimation(nodes_nfailures):
    """Produce a boxplot showing how many times a node failed to
    estimate the slot (producing 0 as estimation).
    """
    x = [int(nid) for nid in nodes_nfailures.keys()]     # node ids
    x.sort()
    x = [str(nid) for nid in x]
    y = [nodes_nfailures[nid] for nid in x]

    ind = np.arange(len(y))
    plt.bar(ind, y)
    plt.xticks(ind, x, rotation=90)
    plt.xlabel("Nodes")
    plt.ylabel("# Failed estimations")
    return x,y

def plot_slot_estimation(nodes_estimates, fliers=False):
    """Produce a boxplot showing the values assumed by the
    slot estimation across floods, by each node.

    NOTE:
    -----
    Slot values are given with the transceiver precision, where
    1 unit corresponds to 31ns.
    To note this, the y label of this chart reports
    a "x31 ns".

        1 DWT_TU ~= 31ns
    """
    x = [int(nid) for nid in nodes_estimates.keys()]     # node ids
    x.sort()
    x = [str(nid) for nid in x]
    y = [nodes_estimates[nid] for nid in x]

    plt.boxplot(y, showfliers=fliers, autorange=True)
    locs, labels = plt.xticks()
    plt.xticks(locs, x, rotation=90)
    plt.xlabel("Nodes")
    plt.ylabel(r"Slot estimation ($\times 31$ ns)")
    return x,y

def plot_flood_trx(nodes_tx, nodes_rx):
    """Plot number of transmission and reception at each flood,
    showing possible variations in their distributions.
    """
    # compute mean value and std of ntx and trx
    mean_tx = {node : np.mean(floods_tx) for node, floods_tx in nodes_tx.items()}
    mean_rx = {node : np.mean(floods_rx) for node, floods_rx in nodes_rx.items()}

    std_tx = {node : np.std(floods_tx) for node, floods_tx in nodes_tx.items()}
    std_rx = {node : np.std(floods_rx) for node, floods_rx in nodes_rx.items()}

    # gather everything in order
    x = [int(node_id) for node_id in nodes_tx.keys()]     # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    n_tx_mean = [mean_tx[node] for node in x]
    n_tx_std  = [std_tx[node]  for node in x]
    n_rx_mean = [mean_rx[node] for node in x]
    n_rx_std  = [std_rx[node]  for node in x]

    # Thanks to
    # https://pythonforundergradengineers.com/python-matplotlib-error-bars.html
    width  = 0.35
    ind = np.arange(len(x))
    b1 = plt.bar(ind        , n_tx_mean, yerr=n_tx_std, width=width, align='center', ecolor='black')
    b2 = plt.bar(ind + width, n_rx_mean, yerr=n_rx_std, width=width, align='center', ecolor='black')
    plt.xticks(ind + width / 2, x)
    plt.xlabel("Nodes")
    plt.ylabel("# packets")
    plt.legend((b1[0], b2[0]), ("Tx", "Rx"))

def plot_trx(nodes_tx, nodes_rx):
    """Show total number of "service" packets (NOT application
    packets) transmitted and received from each node.
    """
    x = [int(nid) for nid in node_tx.keys()]     # node ids
    x.sort()
    x = [str(nid) for nid in x]
    ntx = [nodes_tx[nid] for nid in x]
    nrx = [nodes_rx[nid] for nid in x]

    ind = np.arange(len(x))
    width  = 0.35
    b1 = plt.bar(ind, nrx, width=width)
    b2 = plt.bar(ind + width, ntx, width=width)
    plt.xticks(ind + width / 2, x)
    plt.xlabel("Nodes")
    plt.ylabel("# packets")
    plt.legend((b1[0], b2[0]), ("Rx", "Tx"))

def plot_trx_errors(nodes_nerrs, nodes_nbad_pkt):
    """Plot the number of transmission and reception
    errors, besides the number of bad packet errors.

    * # transmission errors is given by
        # RX errors + # TIMEOUTS errors

    * # bad packet errors is given by
        # BAD_LEN + # BAD HEADER + # BAD PAYLOAD
    """
    x = [int(node_id) for node_id in nodes_nerrs.keys()]    # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    nerr = [nodes_nerrs[nid] for nid in x]
    nbad_pkt = [nodes_nbad_pkt[nid] for nid in x]

    ind = np.arange(len(x))
    width  = 0.35
    b1 = plt.bar(ind, nerr, width=width)
    b2 = plt.bar(ind + width, nbad_pkt, width=width)
    plt.xticks(ind + width / 2, x, rotation=90)
    plt.xlabel("Nodes")
    plt.ylabel("# errors")
    plt.legend((b1[0], b2[0]), ("TRx errors", "Bad packets"))

def plot_trx_error_details(results):
    # reverse key for sorting
    err_list = [k[::-1] for k in results.keys()]
    err_list.sort()
    # put error names to their correct representation
    err_list = [k[::-1] for k in err_list]
    val_list = [results[k] for k in err_list]
    ind = np.arange(len(err_list))
    plt.bar(ind, val_list)
    plt.xticks(ind, err_list, rotation=45)
    plt.title("Error Types")
    plt.ylabel("# errors")

def plot_sync_counters(nodes_sync, nodes_desync):
    """Plot for each node how many times it was able to synchronize,
    and how many to desync."""
    x = [int(node_id) for node_id in nodes_sync.keys()]    # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    y1 = [nodes_sync[node_id]   for node_id in x]   # nsync
    y2 = [nodes_desync[node_id] for node_id in x]   # n_nosync

    ind = np.arange(len(x))
    width  = 0.35
    b1 = plt.bar(ind, y1, width=width)
    b2 = plt.bar(ind + width, y2, width=width)
    plt.xticks(ind + width / 2, x)
    plt.xlabel("Nodes")
    plt.ylabel("# synchronizations")
    plt.legend((b1[0], b2[0]), ("Sync", "No Sync"))

def plot_epoch_estimates(nodes_epochs, fliers=False):
    x = [int(node_id) for node_id in nodes_epochs.keys()]    # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    y = [nodes_epochs[node_id] for node_id in x]

    plt.boxplot(y, showfliers=fliers, autorange=True)
    locs, labels = plt.xticks()
    plt.xticks(locs, x, rotation=90)
    plt.xlabel("Nodes")
    plt.ylabel("Epoch duration (RTimer units)")

# -----------------------------------------------------------------------------
# MAIN-SCRIPT FUNCTIONS
# -----------------------------------------------------------------------------
def simulation_folder_iter(str_start_path):
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

        match = log_reg.match(str(log_path))
        if match:
            name = match.group(1)
            yield name, str(log_path)

def get_current_plot_name():
    """Return an identifier based on the x,y labels
    of the current plot.
    """
    ax = plt.gca()
    xlabel = ax.get_xlabel()
    ylabel = ax.get_ylabel()
    # create a unique filename for the metric, describing the plot
    return str.join("_", re.sub(r"\W+", " ",\
                                (xlabel + " " + ylabel).lower())\
                               .split())

def plot_simulation_results(sim_name, sim_log_path, format_=None, dest_path=None):
    """Plot simulation results either interactively
    or saving them to files.
    """
    if format_ is None:
        format_ = ""
    if dest_path is None:
        dest_path = os.curdir

    # -------------------------------------------------------------------------
    # check how to display plots
    # -------------------------------------------------------------------------
    pdf_fh = None                       # multipage pdf file handler
    if format_ == "":

        # use the interactive session
        pic_out = lambda plot_name: plt.show()

    if format_.lower() == "png":

        # create a folder in the destination directory,
        # containing the images generated
        DEST_FOLDER = os.path.join(dest_path, "figures_{}".format(sim_name))
        if os.path.exists(DEST_FOLDER):
            logger.info("Destination directory {} already exists. Clashing .png files will be overwritten...".format(DEST_FOLDER))
        else:
            os.mkdir(DEST_FOLDER)
        pic_out = lambda plot_name: plt.savefig(os.path.join(DEST_FOLDER, plot_name + ".png"), format="png", papertype="a4", dpi=600)
        print("Printing figures to: {}".format(DEST_FOLDER))

    elif format_.lower() == "pdf-multi":

        # create a multipage PDF
        DEST_PDF = os.path.join(dest_path, "figures_multi_{}.pdf".format(sim_name))
        metadata = {\
                "Title"    : "Results for {}".format(sim_name),\
                "Author"   : "D3S lab - Unversity of Trento",\
                "Subject"  : None,\
                "Keywords" : "Glossy PDR epoch hop-count tx rx error",\
                "CreationDate" : datetime.datetime.today(),\
                "ModDate"  : datetime.datetime.today()}
        pdf_fh = PdfPages(DEST_PDF, metadata=metadata)
        pic_out = lambda plot_filename: pdf_fh.savefig(papertype="a4", dpi=600)
        print("Printing figures to: {}".format(DEST_PDF))

    elif format_.lower() == "pdf":

        # create a folder in the destination directory,
        # containing the images generated
        DEST_FOLDER = os.path.join(dest_path, "figures_{}".format(sim_name))
        if os.path.exists(DEST_FOLDER):
            logger.info("Destination directory {} already exists. Clashing .pdf files will be overwritten...".format(DEST_FOLDER))
        else:
            os.mkdir(DEST_FOLDER)
        pic_out = lambda plot_name: plt.savefig(os.path.join(DEST_FOLDER, plot_name + ".pdf"), format="pdf", papertype="a4", dpi=600)
        print("Printing figures to: {}".format(DEST_FOLDER))

    # -------------------------------------------------------------------------

    log_data = get_log_data(sim_log_path, TESTBED)
    clean_data(log_data, 20)

    # -------------------------------------------------------------------------
    # PLOTTING DATA
    # -------------------------------------------------------------------------

    try:
        pkt_tx, nodes_rx = get_sim_pkt(log_data)
        plt.figure()
        plot_reception_summary(pkt_tx, nodes_rx)
        pic_out("summary")
        plt.close()

        plt.figure()
        nodes_pdr = get_sim_pdr(log_data)
        plot_pdr(nodes_pdr)
        plot_name = get_current_plot_name()
        pic_out(plot_name)
        plt.close()
    except IndexError:
        logger.debug("Couldn't plot pdr")

    try:
        plt.figure()
        nodes_frelay = get_sim_first_relay_counter(log_data)
        plot_first_relay_counter(nodes_frelay)
        plot_name = get_current_plot_name()
        pic_out(plot_name)
        plt.close()
    except:
        logger.debug("Couldn't plot relay counter")

    try:
        nodes_estimates = get_sim_slot_estimation(log_data)
        nodes_nfailures = get_sim_failed_slot_estimation(log_data)
        plt.figure()
        plt.subplot(1,2,1)
        plot_slot_estimation(nodes_estimates, FLIERS)
        plt.subplot(1,2,2)
        plot_failed_slot_estimation(nodes_nfailures)
        plt.tight_layout()
        plot_name = get_current_plot_name()
        pic_out(plot_name)
        plt.close()
    except:
        logger.debug("Couldn't plot slot estimation")

    try:
        nodes_estimates = get_sim_epoch_estimates(log_data)
        plot_epoch_estimates(nodes_estimates, FLIERS)
        plot_name = get_current_plot_name()
        pic_out(plot_name)
        plt.close()
    except:
        logger.debug("Couldn't plot epoch estimations")

    try:
        plt.figure()
        nodes_sync, nodes_desync = get_sim_sync_counters(log_data)
        plot_sync_counters(nodes_sync, nodes_desync)
        plot_name = get_current_plot_name()
        pic_out(plot_name)
        plt.close()
    except:
        logger.debug("Couldn't plot sync counters")

    try:
        plt.figure()
        #plot_trx(log_data)
        nodes_tx, nodes_rx = get_sim_flood_trx(log_data)
        plot_flood_trx(nodes_tx, nodes_rx)
        plot_name = get_current_plot_name()
        pic_out(plot_name)
        plt.close()
    except:
        logger.debug("Couldn't plot trx data")

    try:
        nodes_nerr, nodes_nbad_pkt = get_sim_trx_errors(log_data)
        error_details = get_sim_trx_error_details(log_data)
        plt.figure()
        plt.subplot(1,2,1)
        plot_trx_errors(nodes_nerr, nodes_nbad_pkt)
        plt.subplot(1,2,2)
        plot_trx_error_details(error_details)
        plt.tight_layout()
        plot_name = get_current_plot_name()
        pic_out(plot_name)
        plt.close()
    except:
        logger.debug("Couldn't plot trx detailed errors")
    # -------------------------------------------------------------------------

    if pdf_fh is not None:
        pdf_fh.close()


if __name__ == "__main__":
    import argparse
    import os
    import sys

    BASE_PATH = os.path.dirname(sys.argv[0])
    APP_SOURCE= os.path.abspath(os.path.join(BASE_PATH, "..", "..", "glossy_test.c"))

    # -------------------------------------------------------------------------
    # PARSING ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser()
    # required arguments
    parser.add_argument("log_source",\
            help="The log file to analyse or the folder from which start searching logs")
    # optional args
    parser.add_argument("-s", "--save-plots",\
            nargs="?",\
            const = os.curdir,\
            help="The directory where plot figures are saved.")
    parser.add_argument("-f", "--save-format",\
            nargs = "?",\
            const = "pdf-multi",\
            default = "pdf-multi",\
            choices = ["png", "pdf", "pdf-multi"],\
            help="The format used when saving plots. Either PNG or PDF, single file or one file per page")
    parser.add_argument("-n", "--normal-log",\
            help="When flagged, parsing is performed assuming the log doesn't follow the testbed format",\
            action="store_true")

    args = parser.parse_args()
    # -------------------------------------------------------------------------
    # INPUT CHECKING
    # -------------------------------------------------------------------------

    # set testbed to false if data comes from
    # the testbed
    FLIERS  = False
    TESTBED = True
    if args.normal_log is True:
        TESTBED = False

    format_ = args.save_format
    dest_folder = args.save_plots
    if args.save_plots:

        dest_folder = os.path.abspath(dest_folder)

        if not(os.path.exists(dest_folder) and os.path.isdir(dest_folder)):
            os.mkdir(dest_folder)
    else:
        # if no saving, then save format must be None (force interactive plots)
        format_ = None
    # -------------------------------------------------------------------------

    if os.path.isfile(args.log_source):
        log_reg = re.compile(r"(?:.*/)*(.*).log$")
        match = log_reg.match(args.log_source)
        if match:
            name = match.group(1)
            plot_simulation_results(name, args.log_source, format_, dest_folder)
        else:
            raise ValueError("The file given is not a log file")

    elif os.path.isdir(args.log_source):

        # avoid doing an interactive session in this case, even if asked (too
        # much plots)
        if format_ is None:
            print("Interactive session unavailable when directories are given")
            sys.exit(0)

        for sim_name, log_path in simulation_folder_iter(args.log_source):
            plot_simulation_results(sim_name, log_path, format_, dest_folder)


