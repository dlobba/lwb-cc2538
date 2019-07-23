#!/usr/bin/env python3
"""Module used to gather information direcyly from source code.
"""
import re

def get_glossy_test_conf(source_file="./glossy_test.c"):
    """Extract configuration define in the glossy_test.c file.

    Params:
    -------

    source_path: The path to the glossy_test.c file

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
    period, slot, guard, ntx = (0,0,0,0)

    with open(source_file, "r") as fh:
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

    params = (period, slot, guard, ntx)
    return params


if __name__ == "__main__":
    pass
