#!/usr/bin/python3
import re
import logging

from functools import reduce

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
logging.getLogger(__name__).setLevel(level=logging.DEBUG)

class WrongFloodStatsException(Exception):
    default_msg = "The number of flood statistics is not the"\
            " same for all floods. Check out the logs for"\
            " strange behaviours!"
    def __init__(self, msg=None, data=None):
        super().__init__(msg)
        self.data = data

class WrongGlossyStatsException(Exception):
    default_msg = "The number of glossy statistics is not the"\
            " same for all nodes. Check out the logs for"\
            " strange behaviours!"
    def __init__(self, msg=None, data=None):
        super().__init__(msg)
        self.data = data


# -----------------------------------------------------------------------------
# JSON ENTRY KEYS
# -----------------------------------------------------------------------------
NODES_ENTRY     = "nodes"
NODE_ENTRY      = "node"
BROADCAST_ENTRY = "broadcast"
FLOODS_ENTRY    = "floods"
FLOOD_ENTRY     = "pkt_seqno"
GLOSSY_ENTRY    = "glossy_stats"
APP_ENTRY       = "app_stats"
SEQNO_ATTR      = "pkt_seqno"
REF_RELAY_CNT_ATTR  = "relay_cnt_t_ref"
T_SLOT_ATTR     = "T_slot"
N_TX_ATTR       = "n_tx"
N_RX_ATTR       = "n_rx"
N_RX_ERR_ATTR      = "n_rx_err"
N_RX_TIMEOUT_ATTR  = "rx_to"
REL_CNT_FIRST_RX_ATTR      = "relay_cnt_first_rx"
N_SYNC_ATTR    = "n_sync"
N_NO_SYNC_ATTR = "n_nosync"
RTIMER_EPOCH_ATTR = "epoch_rtimer"
BAD_LEN_ATTR       = "n_bad_length"
BAD_HEADER_ATTR    = "n_bad_header"
BAD_PAYLOAD_ATTR   = "n_bad_payload"

# -----------------------------------------------------------------------------
# SPECIFIC ERRORS
# -----------------------------------------------------------------------------
RF_ERROR_ATTR         = "rf_err"
CRC_ERROR_ATTR        = "bad_crc"

# -----------------------------------------------------------------------------
# Accepted keys: keys that can be found while parsing
# -----------------------------------------------------------------------------
GLOSSY_FLOOD_KEYS = [
    "n_T_slots",
    "T_slot",
    "relay_cnt_t_ref",
    "tref_ts",
    "T_slot_estimated"
]
GLOSSY_STATS_KEYS = [
    N_RX_ATTR,
    N_TX_ATTR,
    REL_CNT_FIRST_RX_ATTR,
    BAD_LEN_ATTR, BAD_HEADER_ATTR, BAD_PAYLOAD_ATTR,
]
ERROR_KEYS = [
        N_RX_ERR_ATTR, N_RX_TIMEOUT_ATTR,
        CRC_ERROR_ATTR,
        RF_ERROR_ATTR
]
ALLOWED_KEYS = GLOSSY_FLOOD_KEYS + GLOSSY_STATS_KEYS + ERROR_KEYS
# -----------------------------------------------------------------------------
# REGEX
# -----------------------------------------------------------------------------
TESTBED_RPI_PREFIX = r"\[\d+-\d+-\d+\s+\d+:\d+:\d+,\d+\]"\
        "\s+\w+:[\w0-9\-_.]+:\s+(\d+)\s*<\s*(.*)"

GLOSSY_LOG = r"^\[\s*([\w0-9-_]+)\s*\]\s*(.*)"
GLOSSY_RELAY_CNT = r"^\[GLOSSY_INFO\]\s*Relay_cnt:\s*(\d+)"
GLOSSY_INIT_MSG = r"^Starting Glossy.*"
# For some strange reason, fireflies in the testbed don't print the
# the following message, which occur before "Starting Glossy"
# GLOSSY_INIT_MSG = r"Glossy successfully initialised"


# ERROR REGEX
BROKEN_LABEL = r"^\[[^\]]*$"
# sync regex
SYNC    = "Synced"
NO_SYNC = "Not Synced"
END_TEST = r"testbed-server:\s+end\s+test"
# -----------------------------------------------------------------------------
FILTER_RULES = [
        GLOSSY_INIT_MSG,\
        r"^\[GLOSSY_PAYLOAD\]",\
        r"^\[GLOSSY_FLOOD_DEBUG\]",\
        r"^\[GLOSSY_STATS(?:_\d+)\]",\
        r"^\[GLOSSY_BROADCAST\]",\
        r"^\[APP_STATS\]",\
        r"^\[APP_DEBUG\]",\
        r"^\[APP_INFO\]",\
        GLOSSY_RELAY_CNT
]
# -----------------------------------------------------------------------------
def filter_log(log, rules):
    """
    Return None if there is no rule in rules matching
    the log.

    Return the log if it matches a rule or None.
    """
    for rule in rules:
        if re.match(rule, log):
            return log
    return None

def parse_glossy_stats(log_content):
    """
    Return a key value tuple out of a log line following
    the format:
      stat1 val1, stat2 val2, ...

    Note the log has been already cleaned from its tag.
    """
    key_val = {k:int(v) for k,v in \
            (m.groups() for m in re.finditer("(\w+):?\s+(\d+)", log_content))}
    # check keys, if something is wrong, drop the entire content
    for key in key_val.keys():
        if not key in ALLOWED_KEYS:
            logger.debug("No matching key: {}. Dropping log: {}".format(key, log_content))
            return ()
    # return k-v pairs as a generator
    for k,v in key_val.items():
        yield k,v

def convert_log_content(log):
    """Remove special characters and remove bytestring notation"""
    if log[0] == "b":
        # return string without bytecode repr -> b''
        log = log[2:-1]
    # replace special characters with a single blank space
    log = re.sub(r"(?:\\t|\\n)+", " ", log)
    return log

def parse_logs(filepath, testbed=True):
    """
    Return <node_id, log> pairs from the sequence
    of logs contained in the given file.
    """
    if testbed is True:
        prefix = re.compile(TESTBED_RPI_PREFIX)
    else:
        prefix = re.compile("(.*)")
    end_rex = re.compile(END_TEST.lower())
    with open(filepath, "r") as fh:
        line_cnt = 0
        for line in fh:
            line_cnt += 1
            match_end = end_rex.findall(line.lower())
            if match_end:
                # exit the for loop
                logger.debug("End of test encountered at line {}. Stop parsing..."\
                        .format(line_cnt))
                break
            for match in prefix.finditer(line):
                if testbed is True:
                    node_id, log = match.groups()
                    log = convert_log_content(log)
                else:
                    # set node id to 0 for standalone log
                    node_id = "0"
                    log = match.group(0)
                match = filter_log(log, FILTER_RULES)
                err_match = re.match(BROKEN_LABEL, log)
                if err_match:
                    logger.debug("Possible broken label at line {}".format(line_cnt))
                    logger.debug("Log: {}".format(log))
                if not match:
                    continue
                yield node_id, log

def get_log_data(filename, testbed=True):
    """
    Produce a single dictionary containing the aggregated
    data for each node id.

    With the following hierarchy:

    nodes
    |-------|---> node        : <node_id>
            |---> broadcast   : <list of pkt seqno bcast>
            |---> glossy_stats
            |       |---> glossy_stat1 : val1
            |       |---> glossy_stat2 : val2
            |       |---> glossy_stat3 : val3
            |
            |---> floods
                    |-------|---> pkt_seqno    : <seqno_1>
                    |       |---> glossy_stat1 : val1
                    |       |---> glossy_stat2 : val2
                    |       |---> glossy_stat3 : val3
                    |
                    |-------|---> pkt_seqno    : <seqno_2>
                            |---> glossy_stat1 : val1
                            |---> glossy_stat2 : val2
                            |---> glossy_stat3 : val3

    The function guarantees that every flood or glossy entry,
    respectively, has the same number of entries.
    """
    # log data
    nodes        = set()                # Set of nodes
    flood_inits  = {}                   # For each node keep a list of the seqno of the
                                        #   pkt broadcast
    flood_stats  = {}                   # Flood statistics, for each received packet seqno
                                        #   store the set of flood statistics
    glossy_stats = {}                   # Whole execution statistics
    # temporary structures
    current_flood = {}                  # For each node store the last pkt received
    app_stats    = {}                   # For each node store application data information

    unmanaged_labels = set()
    """
    NOTE:
    * Glossy init message is seen before any other log
        -> hence an active is automatically added
           to the flood_stats and glossy_stats dicts
    * The received packet is seen before printing
      the corresponding stats (both flood stats and glossy stats)
      Hence, when seeing the debug stats log, the key for the
      corresponding flood will be already present
    """
    for node_id, log in parse_logs(filename, testbed=testbed):
        tagged_log = re.match(GLOSSY_LOG, log)

        if tagged_log:
            label, content = tagged_log.groups()

            if label.startswith("GLOSSY_STATS"):

                # keep only the last glossy stat, so whenever
                # new values with same keys are encountered they will
                # replace the current one.
                # If there are no problems e.g. log truncation from the
                # testbed etc. THEN this is ok
                for param, value in parse_glossy_stats(content):
                    glossy_stats[node_id][param] = int(value)

            elif label == "GLOSSY_FLOOD_DEBUG":

                for param, value in parse_glossy_stats(content):
                    value = int(value)
                    flood = current_flood[node_id]
                    flood_stats[node_id][flood][param] = value

            elif label == "GLOSSY_PAYLOAD":

                pkt_seqno = re.match("rcvd_seq\s*(\d+)", content).groups()[0]
                pkt_seqno = int(pkt_seqno)
                flood_stats[node_id][pkt_seqno] = {FLOOD_ENTRY : pkt_seqno}
                current_flood[node_id] = pkt_seqno

            elif label == "GLOSSY_BROADCAST":

                try:
                    match = re.match(r"\s*sent_seq\s+(\d+),\s+payload_len\s+\d+",\
                            content)
                    pkt_seqno = int(match.group(1))

                except (ValueError, AttributeError):
                    raise ValueError("Invalid regexp for capturing pkt seqno within GLOSSY_BROADCAST")
                flood_inits[node_id].append(pkt_seqno)

            elif label == "APP_STATS":
                try:
                    match = re.match(
                        r"\s*n_rx\s+(\d+)(?:,)\s*n_tx\s+(\d+)(?:,)",\
                        content)
                    if not match:
                        logger.debug("No matching n_tx, t_rx in APP_STATS. Dropping log: {}".format(content))
                    else:
                        nrx, ntx = match.groups()
                        nrx = int(nrx)
                        ntx = int(ntx)
                        pkt_seqno = current_flood[node_id]
                        flood_stats[node_id][pkt_seqno][N_TX_ATTR] = ntx
                        flood_stats[node_id][pkt_seqno][N_RX_ATTR] = nrx

                except (ValueError, AttributeError):
                    raise ValueError("Invalid regexp for capturing n_tx, t_rx within APP_STATS")

            elif label == "APP_DEBUG":

                strip_content = content.strip()
                if strip_content == SYNC:

                    app_stats[node_id][N_SYNC_ATTR]    += 1

                elif strip_content == NO_SYNC:

                    app_stats[node_id][N_NO_SYNC_ATTR] += 1

                elif strip_content.lower().startswith("Epoch_diff".lower()):

                    match = re.match("Epoch_diff\s+rtimer\s+(\d+)",\
                            strip_content)
                    if not match:
                        logger.debug("No matching epoch diff info. Dropping log: {}".format(strip_content))
                    else:
                        rtimer = match.group(1)
                        rtimer = int(rtimer)
                        app_stats[node_id][RTIMER_EPOCH_ATTR].append(rtimer)

                else:
                    logger.debug("Unmanaged {} tag information: {}"\
                            .format(label, strip_content))
            elif label == "APP_INFO":
                logger.debug("Failed to init flood. Retrying on next slot")
            else:

                if label in unmanaged_labels:
                    continue
                logger.debug("Unmanaged unfiltered logged TAG:{}".format(label))
                unmanaged_labels.add(label)

        # if log doesn't match LOG, then it could be a glossy
        # init message
        elif re.match(GLOSSY_INIT_MSG, log):
            nodes.add(node_id)
            flood_inits[node_id]  = []
            flood_stats[node_id]  = {}
            glossy_stats[node_id] = {}
            app_stats[node_id]    = {\
                    N_SYNC_ATTR: 0, N_NO_SYNC_ATTR: 0,\
                    RTIMER_EPOCH_ATTR: []}

    # --------------------------------------------------------------------------
    # DATA CHECK
    # --------------------------------------------------------------------------
    if len(flood_inits) == 0:
        raise ValueError("No data has been collected, check out the log format!")

    def key_value_pair_iterator(dict_):
        for key in dict_.keys():
            for value in dict_[key].keys():
                yield key, value
    flood_stats_len = [len(flood_stats[node][flood])\
            for node, flood in key_value_pair_iterator(flood_stats)]
    floods_ok = reduce(lambda x, y: x == y,
            map(lambda z: z == flood_stats_len[0],
                flood_stats_len))
    glossy_stats_len = [len(glossy_stats[node]) for node in glossy_stats.keys()]
    def c(x,y):
        if x > 0 and y > 0:
            return x == y
        else:
            return True
    glossy_ok = reduce(c,
            map(lambda z: z == glossy_stats_len[0],
                glossy_stats_len))

    if not floods_ok:
        logger.debug("Nodes have different amount of floods information.")
    if not glossy_ok:
        logger.debug("Nodes have different amount of glossy stats information")
    # --------------------------------------------------------------------------
    # AGGREGATE COLLECTED DATA
    # --------------------------------------------------------------------------
    data = {node_id : {NODE_ENTRY : node_id} for node_id in nodes}
    for node_id in data.keys():
        # if node has passed through the init message, then
        # its id is as key within any log data structure
        if node_id not in flood_inits:
            continue
        data[node_id][BROADCAST_ENTRY] = flood_inits[node_id].copy()
        data[node_id][FLOODS_ENTRY]    = list(flood_stats[node_id].values()).copy()
        data[node_id][GLOSSY_ENTRY]    = glossy_stats[node_id].copy()
        data[node_id][APP_ENTRY]       = app_stats[node_id].copy()

    data = {NODES_ENTRY : list(data.values())}
    return data


if __name__ == "__main__":
    import os
    import json
    import argparse
    # -------------------------------------------------------------------------
    # PARSING ARGUMENTS
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser()
    # required arguments
    parser.add_argument("log_file",\
            help="The log file to parse")
    # optional args
    parser.add_argument("-s", "--save-json",\
            help="The file where the data will be dumped in JSON format.")
    parser.add_argument("-n", "--normal-log",\
            help="When flagged, parsing is performed assuming the log doesn't follow the testbed format",\
            action="store_true")
    args = parser.parse_args()

    testbed = True
    if args.normal_log is True:
        testbed = False

    try:
        data = get_log_data(args.log_file, testbed)
    except (WrongFloodStatsException, WrongGlossyStatsException) as e:
        data = e.data
        raise e

    if args.save_json:
        dest_file = args.save_json
        if dest_file.split(".")[-1].lower() != "json":
            dest_file += ".json"
        with open(dest_file, "w") as fh:
            json.dump(data, fh)

