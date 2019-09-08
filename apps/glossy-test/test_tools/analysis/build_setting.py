#!/usr/bin/python3
import re

from collections import OrderedDict

# -----------------------------------------------------------------------------
# SETTINGS
# -----------------------------------------------------------------------------
SIM_SETTINGS = "settings.csv"
# fields
SIM_NTX = "ntx"
SIM_INITIATOR = "initiator"
SIM_TXPOWER = "txpower"
SIM_FRAMESIZE = "frame_size"
SIM_SLOT_DURATION_MS = "slot_ms"
SIM_PERIOD_DURATION_MS = "period_ms"
SIM_GUARD_TIME_MS = "guard_ms"
SIM_CHANNEL = "channel"
# temporary field
SIM_PAYLOAD_LEN = "payload_len"

# HEADERS
SETTINGS_HEADER = [SIM_CHANNEL, SIM_TXPOWER, SIM_NTX, SIM_FRAMESIZE, SIM_INITIATOR]
SETTINGS_ABBREV = ["ch", "txpower", "ntx", "frame", "init"]

SETTINGS_FULL = [
        SIM_PERIOD_DURATION_MS,  SIM_SLOT_DURATION_MS, SIM_GUARD_TIME_MS,\
        SIM_CHANNEL, SIM_TXPOWER,\
        SIM_FRAMESIZE, SIM_NTX, SIM_INITIATOR]


FILTER_RULES = {
        "(?i)cc2538_rf_channel:\s+(\d+)": SIM_CHANNEL,\
        "(?i)cc2538_rf_tx_power:\s+(\w+)": SIM_TXPOWER,\
        "(?i)initiator_id:\s+(\d+)": SIM_INITIATOR,\
        "(?i)payload_data_len:\s+(\d+)": SIM_PAYLOAD_LEN,\
        "(?i)glossy_n_tx:\s+(\d+)": SIM_NTX,\
        "(?i)glossy_period:\s+(.*)": SIM_PERIOD_DURATION_MS,\
        "(?i)glossy_slot:\s+(.*)": SIM_SLOT_DURATION_MS,\
        "(?i)glossy_guard:\s+(.*)": SIM_GUARD_TIME_MS\
}

def match_filter(log, rules):
    """
    Return None if there is no rule in rules matching
    the log.

    Return the log if it matches a rule or None.
    """
    for rule in rules:
        match = re.match(rule, log)
        if match:
            return rules[rule], match
    return None, None

def get_pkt_size(payload):
    # header (4B) + seqno (4B) + payload + crc(2B)
    return 4 + 4 + payload + 2

def parse_build_setting_lines(lines):
    RTIMER_SYMBOLIC = r"rtimer_second"
    RTIMER_SECOND = 32768
    PRECISION  = 1000 # ms
    # assume millisecond granularity
    # if this is not sufficient (IT SHOULD BE!) throw an error an inform
    # the user that this code should be changed to the new precision
    # by changing the value of RTIMER_VALUE

    settings = {}
    for line in lines:
        rule, match = match_filter(line, FILTER_RULES)
        if rule == SIM_CHANNEL:
            settings[SIM_CHANNEL] = int(match.group(1))

        elif rule == SIM_TXPOWER:
            settings[SIM_TXPOWER] = match.group(1)

        elif rule == SIM_INITIATOR:
            settings[SIM_INITIATOR] = int(match.group(1))

        elif rule == SIM_PAYLOAD_LEN:
            settings[SIM_FRAMESIZE] = get_pkt_size(int(match.group(1)))

        elif rule == SIM_NTX:
            settings[SIM_NTX] = int(match.group(1))

        elif rule == SIM_PERIOD_DURATION_MS:
            duration = match.group(1)
            duration = int(eval(duration) / RTIMER_SECOND * PRECISION)
            settings[SIM_PERIOD_DURATION_MS] = duration

        elif rule == SIM_SLOT_DURATION_MS:
            duration = match.group(1)
            duration = int(eval(duration) / RTIMER_SECOND * PRECISION)
            settings[SIM_SLOT_DURATION_MS] = duration

        elif rule == SIM_GUARD_TIME_MS:
            duration = match.group(1)
            duration = int(eval(duration) / RTIMER_SECOND * PRECISION)
            settings[SIM_GUARD_TIME_MS] = duration

    return settings

def parse_build_setting(filesettings):
    with open(filesettings, "r") as fh:
        return parse_build_setting_lines(fh)

def get_settings_row(settings):
    values = [settings[h] for h in SETTINGS_HEADER]
    return values

def get_radio_channel(settings):
    return settings[SIM_CHANNEL]

def get_sim_name(settings):
    values = [settings[v] for v in SETTINGS_HEADER]
    values = ["%s%s" % (k, str(v)) for k,v in zip(SETTINGS_HEADER, values)]
    return str.join("_", values)

def get_sim_name_abbrev(settings):
    values = [str(settings[v]).lower() for v in SETTINGS_HEADER]
    values = ["%s%s" % (k, str(v)) for k,v in zip(SETTINGS_ABBREV, values)]
    return str.join("_", values)


def get_settings_summary(settings):
    summary=OrderedDict([(k, settings[k]) for k in SETTINGS_FULL])
    return summary

if __name__ == "__main__":
    pass
