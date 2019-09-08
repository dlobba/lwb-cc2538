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
from chart_config import init_matplotlib
from navigator import simulation_log_iter

from data_analysis import DAException
from data_analysis import clean_data
from data_analysis import get_sim_pdr, get_sim_first_relay_counter, get_sim_slot_estimation, get_sim_failed_slot_estimation
from data_analysis import get_sim_epoch_estimates
from data_analysis import get_sim_sync_counters
from data_analysis import get_sim_trx, get_sim_flood_trx
from data_analysis import get_sim_trx_errors, get_sim_trx_error_details, get_sim_pkt

# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
logging.getLogger(__name__).setLevel(level=logging.DEBUG)

# higher the criticality for matplotlib logs (so to log **less**)
mpl_logger = logging.getLogger(matplotlib.__name__)
mpl_logger.setLevel(logging.WARNING)
# -----------------------------------------------------------------------------
init_matplotlib()

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

    plt.boxplot(y, showfliers=True, whis=[1,99])
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

def plot_simulation_results(sim_name, sim_log_path, format_=None, dest_path=None, overwrite=False):
    """Plot simulation results either interactively
    or saving them to files.
    """
    if format_ is None:
        format_ = ""
    if dest_path is None:
        dest_path = os.path.dirname(os.path.abspath(sim_log_path))

    # -------------------------------------------------------------------------
    # check how to display plots
    # -------------------------------------------------------------------------
    pdf_fh = None                       # multipage pdf file handler
    plot_output = None
    if format_ == "":

        # use the interactive session
        pic_out = lambda plot_name: plt.show()

    if format_.lower() == "png":

        # create a folder in the destination directory,
        # containing the images generated
        DEST_FOLDER = os.path.join(dest_path, "figures_{}".format(sim_name))
        plot_output = DEST_FOLDER
        if os.path.exists(DEST_FOLDER):

            if overwrite is True:
                logger.info("Destination directory {} already exists. Clashing .png files will be overwritten...".format(DEST_FOLDER))
            else:
                logger.info("Destination directory {} already exists. Skipping computation...".format(DEST_FOLDER))
                return

        else:
            os.mkdir(DEST_FOLDER)
        pic_out = lambda plot_name: plt.savefig(os.path.join(DEST_FOLDER, plot_name + ".png"), format="png", papertype="a4", dpi=600)
        print("Printing figures to: {}".format(DEST_FOLDER))

    elif format_.lower() == "pdf-multi":

        # create a multipage PDF
        DEST_PDF = os.path.join(dest_path, "figures_multi_{}.pdf".format(sim_name))
        plot_output = DEST_PDF
        if os.path.exists(DEST_PDF):
            if overwrite is True:
                logger.info("Destination file {} already exists. It will be overwritten...".format(DEST_PDF))
            else:
                logger.info("Destination file {} already exists. Skipping computation...".format(DEST_PDF))
                return

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
        plot_output = DEST_FOLDER
        if os.path.exists(DEST_FOLDER):
            if overwrite is True:
                logger.info("Destination directory {} already exists. Clashing .pdf files will be overwritten...".format(DEST_FOLDER))
            else:
                logger.info("Destination directory {} already exists. Skipping compuation...".format(DEST_FOLDER))
                return
        else:
            os.mkdir(DEST_FOLDER)
        pic_out = lambda plot_name: plt.savefig(os.path.join(DEST_FOLDER, plot_name + ".pdf"), format="pdf", papertype="a4", dpi=600)
        print("Printing figures to: {}".format(DEST_FOLDER))

    # -------------------------------------------------------------------------

    try:
        print("-"*40 + "\nProcessing file:\n%s\n" % sim_log_path + "-"*40)
        log_data = get_log_data(sim_log_path)
        clean_data(log_data, 20)

        # -------------------------------------------------------------------------
        # PLOTTING DATA
        # -------------------------------------------------------------------------

        try:
            pkt_tx, nodes_rx, not_received = get_sim_pkt(log_data)

            # display info on the effective # packets
            # received by each node
            print("Number of packets considered: {}".format(pkt_tx))
            print("-" * 40)
            for nid, nrx in nodes_rx.items():
                print("Node {}: {}".format(str(nid).zfill(2), nrx))

            not_received = {k:v for k,v in not_received.items() if len(v) > 0}
            if len(not_received) > 0:
                print("-"*40 + "\nNOT RECEIVED\n" + "-"*40)
                for nid, nr in not_received.items():
                    pkts = [str(seqno) for seqno in list(nr)]
                    missing_pkts = str.join(", ", pkts)
                    print("Id %s: %s" % (str(nid).zfill(2), missing_pkts))
            else:
                print("Every packet has been received")

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
        except DAException as e:
            raise e
        except Exception as e:
            logger.debug("Couldn't plot pdr")

        try:
            plt.figure()
            nodes_frelay = get_sim_first_relay_counter(log_data)
            plot_first_relay_counter(nodes_frelay)
            plot_name = get_current_plot_name()
            pic_out(plot_name)
            plt.close()
        except DAException as e:
            raise e
        except Exception as e:
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
        except DAException as e:
            raise e
        except Exception as e:
            logger.debug("Couldn't plot slot estimation")

        try:
            nodes_estimates = get_sim_epoch_estimates(log_data)
            plot_epoch_estimates(nodes_estimates, FLIERS)
            plot_name = get_current_plot_name()
            pic_out(plot_name)
            plt.close()
        except DAException as e:
            raise e
        except Exception as e:
            logger.debug("Couldn't plot epoch estimations")

        try:
            plt.figure()
            nodes_sync, nodes_desync = get_sim_sync_counters(log_data)
            plot_sync_counters(nodes_sync, nodes_desync)
            plot_name = get_current_plot_name()
            pic_out(plot_name)
            plt.close()
        except DAException as e:
            raise e
        except Exception as e:
            logger.debug("Couldn't plot sync counters")

        try:
            plt.figure()
            #plot_trx(log_data)
            nodes_tx, nodes_rx = get_sim_flood_trx(log_data)
            plot_flood_trx(nodes_tx, nodes_rx)
            plot_name = get_current_plot_name()
            pic_out(plot_name)
            plt.close()
        except DAException as e:
            raise e
        except Exception as e:
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
        except DAException as e:
            raise e
        except Exception as e:
            logger.debug("Couldn't plot trx detailed errors")
        # -------------------------------------------------------------------------

        if pdf_fh is not None:
            pdf_fh.close()
    except BaseException as e:
        if pdf_fh is not None:
            pdf_fh.close()
        if os.path.isfile(plot_output):
            os.remove(plot_output)
        else:
            shutil.rmtree(plot_output)
        raise e


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
            const = True,\
            help="The directory where plot figures are saved.")
    parser.add_argument("-o", "--overwrite",\
            nargs = "?",\
            const = True,\
            default = False,\
            help="Overwrite output files if already existing")
    parser.add_argument("-f", "--save-format",\
            nargs = "?",\
            const = "pdf-multi",\
            default = "pdf-multi",\
            choices = ["png", "pdf", "pdf-multi"],\
            help="The format used when saving plots. Either PNG or PDF, single file or one file per page")

    args = parser.parse_args()
    # -------------------------------------------------------------------------
    # INPUT CHECKING
    # -------------------------------------------------------------------------

    # set testbed to false if data comes from
    # the testbed
    FLIERS  = False

    format_ = args.save_format
    if args.save_plots is True:
        dest_folder = None
    elif args.save_plots:

        dest_folder = os.path.abspath(args.save_plots)
        if not(os.path.exists(dest_folder) and os.path.isdir(dest_folder)):
            os.mkdir(dest_folder)
    else:
        # if no saving, then save format must be None (force interactive plots)
        dest_folder = None
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

        plots_done = 0
        plots_undone = []
        for sim_name, log_path in simulation_log_iter(args.log_source):
            try:
                plot_simulation_results(sim_name, log_path, format_, dest_folder, overwrite=args.overwrite)
                plots_done += 1
            except DAException as e:
                # data analysis exceptions are important, don't skip them
                raise e
            except Exception:
                logger.error("Invalid log found. Skipped: {}".format(log_path))
                plots_undone.append(log_path)
        print("-"*40)
        print("{} simulations successfully processed".format(plots_done))
        print("{} simulations haven't been processed due to errors".format(len(plots_undone)))
        print("-"*40)
        if len(plots_undone) > 0:
            print("Bad logs:\n" + "-"*40)
        for badlog in plots_undone:
            print(badlog)

