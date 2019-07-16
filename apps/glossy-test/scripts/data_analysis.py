#!/usr/bin/python3
import math
import logging

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

from functools import reduce

import dao

from parser import get_log_data
from parser import NODES_ENTRY, NODE_ENTRY, BROADCAST_ENTRY
from parser import FLOODS_ENTRY, GLOSSY_ENTRY
from parser import SEQNO_ATTR, REF_RELAY_CNT_ATTR, T_SLOT_ATTR
from parser import N_TX_ATTR, N_RX_ATTR
from parser import N_RX_ERR_ATTR, N_RX_TIMEOUT_ATTR
from parser import BAD_LEN_ATTR, BAD_HEADER_ATTR, BAD_PAYLOAD_ATTR, REL_CNT_FIRST_RX_ATTR
from parser import APP_ENTRY, N_SYNC_ATTR, N_NO_SYNC_ATTR, RTIMER_EPOCHS_ATTR, DTU_EPOCHS_ATTR

# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
logging.getLogger(__name__).setLevel(level=logging.DEBUG)

# higher the criticality for matplotlib logs (so to log **less**)
mpl_logger = logging.getLogger(matplotlib.__name__)
mpl_logger.setLevel(logging.WARNING)
# -----------------------------------------------------------------------------

def plot_pdr(data):
    """
    1. Determine the number of broadcast performed by all packets
    2. Determine the total number of packets received by any node
    3. For each node, divide the number of packets received by the
       number of packets sent computed in (1)
    """
    broadcasts = dao.select(data, BROADCAST_ENTRY)
    pkt_tx = reduce(lambda x,y: x + y,\
                map(len, broadcasts))
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, num_floods>
    # if node n has flood entry f, then it received at least one packet
    # during that flood
    pkt_rx = {node:len(dao.select(nodes_data[node], FLOODS_ENTRY))\
            for node in nodes_data}
    x = [int(node_id) for node_id in pkt_rx.keys()]         # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    y = [pkt_rx[node_id]/pkt_tx for node_id in x]           # number of pkt received
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
    plt.axhline(y=1, xmin=0, xmax=1, c="red")
    plt.xlabel("Nodes")
    plt.ylabel("PDR")
    return x,y

def plot_num_initiator(data):
    """Produce a boxplot counting how many times each node has been
    the initiator within the total execution time."""
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, <ref_relay_counter>>
    broadcast = {node:len(dao.select(nodes_data[node], BROADCAST_ENTRY))\
            for node in nodes_data}
    return broadcast

def plot_first_relay_counter(data):
    """Produce a box blot of the values
    assumed by the first relay counter during across
    the considered floods."""
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, <ref_relay_counter>>
    ref_relay_cnt = {node:dao.select(nodes_data[node], REF_RELAY_CNT_ATTR)\
            for node in nodes_data}
    x = [int(node_id) for node_id in ref_relay_cnt.keys()]  # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    y = [ref_relay_cnt[node_id] for node_id in x]           # relay counters

    plt.boxplot(y, showfliers=True, autorange=True)
    locs, labels = plt.xticks()
    plt.xticks(locs, x)
    plt.xlabel("Nodes")
    plt.ylabel("First relay counter")
    return x,y

def plot_failed_slot_estimation(data):
    """Produce a boxplot showing how many times a node failed to
    estimate the slot (producing 0 as estimation).
    """
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, <T_slot>>
    node_slots = {node:dao.select(nodes_data[node], T_SLOT_ATTR)\
            for node in nodes_data}
    x = [int(node_id) for node_id in node_slots.keys()]     # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    slots = [node_slots[node_id] for node_id in x]
    # filter slots not equal to 0
    higher_zero_elements = lambda list_: list(filter(lambda el: el == 0, list_))
    zero_list = list(map(higher_zero_elements, slots))
    # count how many zeros are there in each list
    y = list(map(len, zero_list))

    ind = np.arange(len(y))
    plt.bar(ind, y)
    plt.xticks(ind, x)
    plt.xlabel("Nodes")
    plt.ylabel("# Failed estimations")
    return x,y

def plot_slot_estimation(data):
    """Produce a boxplot showing the values assumed by the
    slot estimation across floods, by each node.

    NOTE:
    -----
    Slot values are given with the transceiver precision, where
    1 unit corresponds to 31.25ns.
    To note this, the y label of this chart reports
    a "x31 ns".

        1 DWT_TU ~= 32ns
    """
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, <T_slot>>
    node_slots = {node:dao.select(nodes_data[node], T_SLOT_ATTR)\
            for node in nodes_data}
    x = [int(node_id) for node_id in node_slots.keys()]     # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    y = [node_slots[node_id] for node_id in x]              # slots
    # filter slots equal to 0
    higher_zero_elements = lambda list_: list(filter(lambda el: el > 0, list_))
    y = list(map(higher_zero_elements, y))

    plt.boxplot(y, showfliers=True, autorange=True)
    locs, labels = plt.xticks()
    plt.xticks(locs, x)
    plt.xlabel("Nodes")
    plt.ylabel(r"Slot estimation ($\times 31$ ns)")
    return x,y

def plot_trx(data):
    """Show total number of "service" packets (NOT application
    packets) transmitted and received from each node.
    """
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, glossy_stats>
    node_gstats = {node:dao.select(nodes_data[node], GLOSSY_ENTRY)\
            for node in nodes_data}
    x = [int(node_id) for node_id in node_gstats.keys()]     # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    nrx = []
    ntx = []
    for node_id in x:
        try:
            nrx.append(node_gstats[node_id][N_RX_ATTR])
            ntx.append(node_gstats[node_id][N_TX_ATTR])
        except:
            nrx.append(0)
            ntx.append(0)
    ind = np.arange(len(x))
    width  = 0.35
    b1 = plt.bar(ind, nrx, width=width)
    b2 = plt.bar(ind + width, ntx, width=width)
    plt.xticks(ind + width / 2, x)
    plt.xlabel("Nodes")
    plt.ylabel("# packets")
    plt.legend((b1[0], b2[0]), ("Rx", "Tx"))
    return x, (nrx, ntx)

def plot_trx_errors(data):
    """Plot the number of transmission and reception
    errors, besides the number of bad packet errors.

    * # transmission errors is given by
        # RX errors + # TIMEOUTS errors

    * # bad packet errors is given by
        # BAD_LEN + # BAD HEADER + # BAD PAYLOAD
    """
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, glossy_stats>
    node_gstats = {node:dao.select(nodes_data[node], GLOSSY_ENTRY)\
            for node in nodes_data}
    x = [int(node_id) for node_id in node_gstats.keys()]    # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    nerr = []
    nbad_pkt = []
    for node_id in x:
        try:
            nerr.append(node_gstats[node_id][N_RX_ERR_ATTR]    +\
                node_gstats[node_id][N_RX_TIMEOUT_ATTR])
            nbad_pkt.append(node_gstats[node_id][BAD_LEN_ATTR]     +\
                node_gstats[node_id][BAD_HEADER_ATTR]  +\
                node_gstats[node_id][BAD_PAYLOAD_ATTR])
        except KeyError:
            nerr.append(0)
            nbad_pkt.append(0)

    ind = np.arange(len(x))
    width  = 0.35
    b1 = plt.bar(ind, nerr, width=width)
    b2 = plt.bar(ind + width, nbad_pkt, width=width)
    plt.xticks(ind + width / 2, x)
    plt.xlabel("Nodes")
    plt.ylabel("# errors")
    plt.legend((b1[0], b2[0]), ("TRx errors", "Bad packets"))

def plot_trx_error_details(data):
    # collect all glossy_stats
    node_gstats = dao.select(data, GLOSSY_ENTRY)
    # filter nodes without glossy_stats
    node_gstats = filter(lambda gstats: len(gstats) > 0, node_gstats)
    # aggregate results
    results = reduce(lambda x,y: {k: x[k] + y[k]\
            for k in set(list(x.keys()) + list(y.keys()))}, node_gstats)

    # compute the number of unknown errors:
    nerrs = results[N_RX_ERR_ATTR]    +\
            results[N_RX_TIMEOUT_ATTR]
    results.pop(N_RX_ERR_ATTR)
    results.pop(N_RX_TIMEOUT_ATTR)
    results.pop(BAD_LEN_ATTR)
    results.pop(BAD_HEADER_ATTR)
    results.pop(BAD_PAYLOAD_ATTR)
    results.pop(N_RX_ATTR)
    results.pop(N_TX_ATTR)
    results.pop(REL_CNT_FIRST_RX_ATTR)
    detailed_errors = sum(results.values())
    results["unknown_err"] = nerrs - detailed_errors
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

def plot_sync_counters(data):
    """Plot for each node how many times it was able to syncrhonize,
    and how many to desync."""
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, app_stats>
    node_appstats = {node:dao.select(nodes_data[node], APP_ENTRY)\
            for node in nodes_data}
    x = [int(node_id) for node_id in node_appstats.keys()]    # node ids
    x.sort()
    x = [str(node_id) for node_id in x]

    y1 = [node_appstats[node_id][N_SYNC_ATTR] for node_id in x]     # nsync
    y2 = [node_appstats[node_id][N_NO_SYNC_ATTR] for node_id in x]   # n_nosync

    ind = np.arange(len(x))
    width  = 0.35
    b1 = plt.bar(ind, y1, width=width)
    b2 = plt.bar(ind + width, y2, width=width)
    plt.xticks(ind + width / 2, x)
    plt.xlabel("Nodes")
    plt.ylabel("# synchronizations")
    plt.legend((b1[0], b2[0]), ("Sync", "No Sync"))
    return x, (y1, y2)

def plot_epoch_estimates(data):
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, app_stats>
    node_appstats = {node:dao.select(nodes_data[node], RTIMER_EPOCHS_ATTR)\
            for node in nodes_data}
    x = [int(node_id) for node_id in node_appstats.keys()]    # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    y = [node_appstats[node_id] for node_id in x]

    plt.boxplot(y, showfliers=True, autorange=True)
    locs, labels = plt.xticks()
    plt.xticks(locs, x)
    plt.xlabel("Nodes")
    plt.ylabel("Epoch duration (RTimer units)")

    return x, y

def plot_epoch_estimates_dtu(data):
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, app_stats>
    node_appstats = {node:dao.select(nodes_data[node], DTU_EPOCHS_ATTR)\
            for node in nodes_data}
    x = [int(node_id) for node_id in node_appstats.keys()]    # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    y = [node_appstats[node_id] for node_id in x]

    plt.boxplot(y, showfliers=True, autorange=True)
    locs, labels = plt.xticks()
    plt.xticks(locs, x)
    plt.xlabel("Nodes")
    plt.ylabel("Epoch duration (DW1000 DTU)")

    return x, y


def clean_data(data, offset):
    """Drop initial and terminal floods information.

    1. Determine the set of packets received by at least one node.
    2. Pick the lowest and highest sequence numbers of such set.
    3. Add a +offset to lowest and a -offset to the highest
       and get a continuous sequence of numbers S between

            S = [lowest+offset, highest-offset]

    4. Check that all packets within S have been
       received by at least one node.
       In case remove differing packets from S.
    5. Remove any packet not in S from every node
    6. Remove references of such packets also from the broadcast
       packets sets.
    """
    pkts = [set(pkt_node) for pkt_node in dao.select(data, SEQNO_ATTR)]
    # point 1
    pkt_received_some = reduce(lambda x, y: x.union(y), pkts)
    # point 2 & 3
    # Due to packet corruption, it happened that a node received a
    # a packet with a seqno tremendously high (some billion).
    # This leads to MemoryError when creating a sequence from
    # 0 up to this value.
    # Here we address this problem by trying to create the sequence, if
    # MemoryError occurred, we remove the problematic value from the
    # set and try to compute the sequence again.
    # The problematic flood on the node will be removed. Other nodes
    # will have the correct flood, generating a discrepancy
    # between the set of received packets and the transmitted set.
    sequence_done = False
    pkt_to_remove = set()
    while not sequence_done:
        min_seqno = min(pkt_received_some) + offset
        max_seqno = max(pkt_received_some) - offset
        try:
            pkt_considered = set(range(min_seqno, max_seqno + 1))
            # able to build the sequence, exit the loop
            sequence_done  = True
        except MemoryError:
            problematic_pkt = max(pkt_received_some)
            pkt_received_some.remove(problematic_pkt)
            pkt_to_remove.add(problematic_pkt)
            logger.debug("Possible unexpected delivery on pkt: {}. Removed"\
                    .format(problematic_pkt))
    # point 4
    pkt_diffs = pkt_considered.difference(pkt_received_some)
    for pkt in pkt_diffs:
        pkt_considered.remove(pkt)
    # point 5
    pkt_to_remove.update(\
            pkt_received_some.difference(pkt_considered))
    dao.delete(data, SEQNO_ATTR, pkt_to_remove)
    # point 6
    # remove packets not considered from node broadcasts
    paths = dao.get_paths_for_field(data, BROADCAST_ENTRY)
    path  = paths[0]
    bcast_structures = dao.get_pointer_to(data, path)
    for bcast_structure in bcast_structures:
        new_pkt_bcast = set(bcast_structure[BROADCAST_ENTRY])\
                .difference(pkt_to_remove)
        bcast_structure[BROADCAST_ENTRY] = list(new_pkt_bcast)

    # remove first and last epoch estimates
    paths = dao.get_paths_for_field(data, RTIMER_EPOCHS_ATTR)
    path  = paths[0]
    bcast_structures = dao.get_pointer_to(data, path)
    for bcast_structure in bcast_structures:
        new_epochs_rtimer = bcast_structure[RTIMER_EPOCHS_ATTR][0 + offset : -offset]
        new_epochs_dtu    = bcast_structure[DTU_EPOCHS_ATTR][0 + offset : -offset]
        bcast_structure[RTIMER_EPOCHS_ATTR] = new_epochs_rtimer
        bcast_structure[DTU_EPOCHS_ATTR] = new_epochs_dtu


    # test that the pkt broadcast match those received
    pkt_received  = [set(pkt_node) for pkt_node in dao.select(data, SEQNO_ATTR)]
    pkt_bcast     = [set(pkt_node) for pkt_node in dao.select(data, BROADCAST_ENTRY)]
    pkt_bcast_some    = reduce(lambda x, y: x.union(y), pkt_bcast)
    pkt_received_some = reduce(lambda x, y: x.union(y), pkt_received)
    tx_rx_diff = pkt_bcast_some.symmetric_difference(pkt_received_some)
    if len(tx_rx_diff) != 0:
        logger.debug("Packets received and sent differ!")
        logger.debug("Differing packets: {}".format(tx_rx_diff))
    return True

def save_pic(filename, format_):
    if filename.split(".")[-1].lower() != format_.lower():
        filename += "." + format_
    plt.savefig(filename, format=format_, papertype="a4", dpi=300)
    plt.close()

def save_next_pic(collection_iter, format_):
    try:
        pic = next(collection_iter)
        save_pic(pic, format_)
    except Stopiteration:
        pass


if __name__ == "__main__":
    import argparse
    import os
    # -------------------------------------------------------------------------
    # PARSING ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser()
    # required arguments
    parser.add_argument("log_file",\
            help="The log file to analyse")
    # optional args
    parser.add_argument("-s", "--save-plots",\
            help="The directory where plot figures are saved.")
    parser.add_argument("-n", "--normal-log",\
            help="When flagged, parsing is performed assuming the log doesn't follow the testbed format",\
            action="store_true")

    args = parser.parse_args()
    # -------------------------------------------------------------------------
    # INPUT CHECKING
    # -------------------------------------------------------------------------

    # set testbed to false if data comes from
    # the testbed
    testbed = True
    if args.normal_log is True:
        testbed = False

    if args.save_plots:

        dest_folder = args.save_plots

        if not(os.path.exists(dest_folder) and os.path.isdir(dest_folder)):
            os.mkdir(dest_folder)

        figurenames = [
            "pdr",
            "hop_count",
            "slot_estimation",
            "epoch_estimation",
            "sync_counters",
            "trx_stats",
            "errors"
        ]
        figurepaths = [dest_folder + os.sep + name for name in figurenames]
        figure_iter = iter(figurepaths)
        pic_out = lambda: save_next_pic(figure_iter, "png")
        print("Printing figures to: {}".format(dest_folder))

    else:
        pic_out = plt.show
    # -------------------------------------------------------------------------

    log_data = get_log_data(args.log_file, testbed)
    clean_data(log_data, 20)


    try:
        plt.figure()
        plot_pdr(log_data)
        pic_out()
    except:
        logger.debug("Couldn't plot pdr")

    try:
        plt.figure()
        x,y = plot_first_relay_counter(log_data)
        pic_out()
    except:
        logger.debug("Couldn't plot relay counter")

    try:
        plt.figure()
        plt.subplot(1,2,1)
        plot_slot_estimation(log_data)
        plt.subplot(1,2,2)
        plot_failed_slot_estimation(log_data)
        plt.tight_layout()
        pic_out()
    except:
        logger.debug("Couldn't plot slot estimation")

    try:
        plt.figure()
        plt.subplot(1,2,1)
        plot_epoch_estimates(log_data)
        plt.subplot(1,2,2)
        plot_epoch_estimates_dtu(log_data)
        pic_out()
    except IndexError:
        logger.debug("Couldn't plot epoch estimations")


    try:
        plt.figure()
        plot_sync_counters(log_data)
        pic_out()
    except:
        logger.debug("Couldn't plot sync counters")

    try:
        plt.figure()
        plot_trx(log_data)
        pic_out()
    except:
        logger.debug("Couldn't plot trx data")

    try:
        plt.figure()
        plt.subplot(1,2,1)
        plot_trx_errors(log_data)
        plt.subplot(1,2,2)
        plot_trx_error_details(log_data)
        plt.tight_layout()
        pic_out()
    except:
        logger.debug("Couldn't plot trx detailed errors")
