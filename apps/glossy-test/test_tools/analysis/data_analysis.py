#!/usr/bin/python3
import math
import logging

import numpy as np

from functools import reduce

import dao

from parser import NODES_ENTRY, NODE_ENTRY, BROADCAST_ENTRY
from parser import FLOODS_ENTRY, GLOSSY_ENTRY
from parser import SEQNO_ATTR, REF_RELAY_CNT_ATTR, T_SLOT_ATTR
from parser import N_TX_ATTR, N_RX_ATTR
from parser import N_RX_ERR_ATTR, N_RX_TIMEOUT_ATTR
from parser import BAD_LEN_ATTR, BAD_HEADER_ATTR, BAD_PAYLOAD_ATTR, REL_CNT_FIRST_RX_ATTR
from parser import APP_ENTRY, N_SYNC_ATTR, N_NO_SYNC_ATTR
from parser import RTIMER_EPOCH_ATTR

from source_inspector import get_glossy_test_conf

# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
logging.getLogger(__name__).setLevel(level=logging.DEBUG)
# -----------------------------------------------------------------------------

class DAException(Exception):

    def __init__(self, message):
        super(Exception, self).__init__(message)


def get_sim_pkt(data):
    """
    1. Determine the number of broadcast performed by all packets
    2. Determine the total number of packets received by any node
    3. Determined at each node which are the packets lost
    """
    broadcasts = [set(bcast) for bcast in dao.select(data, BROADCAST_ENTRY)]
    pkt_tx = reduce(lambda x,y: x.union(y),broadcasts)
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, pkt_rx>
    # if node n has flood entry f, then it received at least one packet
    # during that flood
    pkt_rx = {node:set(dao.select(nodes_data[node], SEQNO_ATTR))\
            for node in nodes_data}

    not_received = {node:[] for node in nodes_data}
    for nid, rx in pkt_rx.items():
        if not rx.issubset(pkt_tx):
            logger.error("Received packets are not a subset of those sent in node %s" % str(nid))
            raise DAException("Received packets are not a subset of those sent in node %s" % str(nid))
        not_received[nid] = pkt_tx.difference(rx)

    nodes_pkt = {node_id : len(pkt_rx[node_id]) for node_id in pkt_rx.keys()}
    return len(pkt_tx), nodes_pkt, not_received

def get_sim_pdr(data):
    """
    1. Determine the number of broadcast performed by all packets
    2. Determine the total number of packets received by any node
    3. For each node, divide the number of packets received by the
       number of packets sent computed in (1)
    """
    broadcasts = [set(bcast) for bcast in dao.select(data, BROADCAST_ENTRY)]
    pkt_tx = reduce(lambda x,y: x.union(y),broadcasts)
    nodes_data = dao.group_by(data, NODE_ENTRY)
    pkt_rx = {node:set(dao.select(nodes_data[node], SEQNO_ATTR))\
            for node in nodes_data}

    # check that receveived packet are a subset of those tx
    for nid, rx in pkt_rx.items():
        if not rx.issubset(pkt_tx):
            logger.error("Received packets are not a subset of those sent in node %s" % str(nid))
            raise DAException("Received packets are not a subset of those sent in node %s" % str(nid))

    # return pdr for each node
    nodes_pdr = {node_id : len(pkt_rx[node_id])/len(pkt_tx) for node_id in pkt_rx.keys()}
    return nodes_pdr

# TODO: unused function, remove it
def plot_num_initiator(data):
    """Produce a boxplot counting how many times each node has been
    the initiator within the total execution time."""
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, <ref_relay_counter>>
    broadcast = {node:len(dao.select(nodes_data[node], BROADCAST_ENTRY))\
            for node in nodes_data}
    return broadcast

def get_sim_first_relay_counter(data):
    """Retrieve for each node the set of values
    assumed by the first relay counter during
    the considered floods."""
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, <ref_relay_counter>>
    ref_relay_cnt = {node:dao.select(nodes_data[node], REF_RELAY_CNT_ATTR)\
            for node in nodes_data}
    return ref_relay_cnt

def get_sim_failed_slot_estimation(data):
    """Return how many times a node failed to
    estimate the slot (producing 0 as estimation).
    """
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, <T_slot>>
    node_slots = {node:dao.select(nodes_data[node], T_SLOT_ATTR)\
            for node in nodes_data}

    # filter slots not equal to 0
    higher_zero_elements = lambda list_: list(filter(lambda el: el == 0, list_))
    x = [int(node_id) for node_id in node_slots.keys()]     # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    slots = [node_slots[node_id] for node_id in x]
    zero_list = list(map(higher_zero_elements, slots))
    # count how many zeros are there in each list
    y = list(map(len, zero_list))
    return {x[i] : y[i] for i in range(0, len(x))}

def get_sim_slot_estimation(data):
    """Retrieve the set of values assumed by the
    slot estimation across floods, by each node.

    NOTE:
    -----
    Slot values are returned with the transceiver precision, where
    1 unit corresponds to 31.25ns.
    To note this, the y label of this chart reports
    a "x31 ns".

        1 DWT_TU ~= 32ns
    """
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, <T_slot>>
    node_slots = {node:dao.select(nodes_data[node], T_SLOT_ATTR)\
            for node in nodes_data}
    # filter slots equal to 0
    higher_zero_elements = lambda list_: list(filter(lambda el: el > 0, list_))
    x = [int(node_id) for node_id in node_slots.keys()]     # node ids
    x.sort()
    x = [str(node_id) for node_id in x]
    y = [node_slots[node_id] for node_id in x]              # slots
    y = list(map(higher_zero_elements, y))
    return {x[i] : y[i] for i in range(0, len(x))}

def get_sim_flood_trx(data):
    """Return number of transmission and reception at each flood,
    showing possible variations in their distributions.
    """
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, floods_stats>
    node_fstats = {node:dao.select(nodes_data[node], FLOODS_ENTRY)\
            for node in nodes_data}

    # for each node, collect info on rx and tx within each flood.
    node_tx = {node : np.array(dao.select(node_fstats[node], N_TX_ATTR)) for node in node_fstats.keys()}
    node_rx = {node : np.array(dao.select(node_fstats[node], N_RX_ATTR)) for node in node_fstats.keys()}
    return node_tx, node_rx

# TODO this is not used anymore
def get_sim_trx(data):
    """Show total number of "service" packets (NOT application
    packets) transmitted and received from each node.
    """
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, glossy_stats>
    node_gstats = {node:dao.select(nodes_data[node], GLOSSY_ENTRY)\
            for node in nodes_data}
    nodes_tx = {}
    nodes_rx = {}
    for node_id in node_gstats.keys():
        try:
            nodes_rx[node_id] = node_gstats[node_id][N_RX_ATTR]
            nodes_tx[node_id] = node_gstats[node_id][N_TX_ATTR]
        except:
            nodes_rx[node_id] = 0
            nodes_rx[node_id] = 0
    return nodes_tx, nodes_rx

def get_sim_trx_errors(data):
    """Retrieve the number of transmission and reception
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
    nerr = {}
    nbad_pkt = {}
    for node_id in node_gstats:
        try:
            nerr[node_id] = node_gstats[node_id][N_RX_ERR_ATTR]    +\
                            node_gstats[node_id][N_RX_TIMEOUT_ATTR]

            nbad_pkt[node_id] = node_gstats[node_id][BAD_LEN_ATTR]     +\
                                node_gstats[node_id][BAD_HEADER_ATTR]  +\
                                node_gstats[node_id][BAD_PAYLOAD_ATTR]
        except KeyError:
            nerr[node_id] = 0
            nbad_pkt[node_id] = 0
    return nerr, nbad_pkt

def get_sim_trx_error_details(data):
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
    return results

def get_sim_sync_counters(data):
    """Retrieve for each node how many times it was able to synchronize,
    and how many to desync."""
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, app_stats>
    node_appstats = {node:dao.select(nodes_data[node], APP_ENTRY)\
            for node in nodes_data}

    nsync = {node_id : node_appstats[node_id][N_SYNC_ATTR] \
            for node_id in node_appstats.keys()}

    ndesync = {node_id : node_appstats[node_id][N_NO_SYNC_ATTR] \
            for node_id in node_appstats.keys()}
    return nsync, ndesync

def get_sim_epoch_estimates(data):
    nodes_data = dao.group_by(data, NODE_ENTRY)
    # compute map <node, app_stats>
    node_appstats = {node:dao.select(nodes_data[node], RTIMER_EPOCH_ATTR)\
            for node in nodes_data}
    return {node_id : node_appstats[node_id] for node_id in node_appstats.keys()}

def clean_data(data, offset):
    """Drop initial and terminal floods information.

    1. the set of packets considered is the set of packet
       broadcast by any node, reduced by an offset to remove
       marginal floods

    2. Any flood corresponding to a sequence number different from
      the set given by 1, is discarded
    2. Remove references to discarded packet also from the broadcast
       packets sets.
    """
    pkt_bcast     = [set(pkt_node) for pkt_node in dao.select(data, BROADCAST_ENTRY)]
    pkt_bcast_some    = reduce(lambda x, y: x.union(y), pkt_bcast)
    pkt_considered = list(pkt_bcast_some)[0 + offset : -offset]

    pkt_received  = [set(pkt_node) for pkt_node in dao.select(data, SEQNO_ATTR)]
    pkt_received_some = reduce(lambda x, y: x.union(y), pkt_received)

    to_remove = set(pkt_bcast_some).union(pkt_received_some).difference(set(pkt_considered))
    dao.delete(data, SEQNO_ATTR, to_remove)

    # remove packets not considered from node broadcasts
    paths = dao.get_paths_for_field(data, BROADCAST_ENTRY)
    path  = paths[0]
    bcast_structures = dao.get_pointer_to(data, path)
    for bcast_structure in bcast_structures:
        new_pkt_bcast = set(bcast_structure[BROADCAST_ENTRY])\
                .difference(to_remove)
        bcast_structure[BROADCAST_ENTRY] = list(new_pkt_bcast)

    # remove first and last epoch estimates
    paths = dao.get_paths_for_field(data, RTIMER_EPOCH_ATTR)
    path  = paths[0]
    bcast_structures = dao.get_pointer_to(data, path)
    for bcast_structure in bcast_structures:
        new_epoch_rtimer = bcast_structure[RTIMER_EPOCH_ATTR][0 + offset : -offset]
        bcast_structure[RTIMER_EPOCH_ATTR] = new_epoch_rtimer

    # test that the pkt broadcast match those received, and vice versa
    pkt_bcast     = [set(pkt_node) for pkt_node in dao.select(data, BROADCAST_ENTRY)]
    pkt_bcast_some    = reduce(lambda x, y: x.union(y), pkt_bcast)
    pkt_received  = [set(pkt_node) for pkt_node in dao.select(data, SEQNO_ATTR)]
    pkt_received_some = reduce(lambda x, y: x.union(y), pkt_received)
    tx_rx_diff = pkt_bcast_some.symmetric_difference(pkt_received_some)
    if len(tx_rx_diff) != 0:
        logger.debug("Packets received and sent differ!")
        logger.debug("Differing packets: {}".format(tx_rx_diff))
        raise DAException("Packets received and sent differ!")

    return True


if __name__ == "__main__":
    pass
