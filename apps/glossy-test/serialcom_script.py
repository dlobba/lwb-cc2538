import testbed.Testbed
import logging
import time

logger = logging.getLogger(__name__)

def run_test(testbed):
    logger.info("Script begins")

    init_id = 0
    while True:
        for n in testbed.activeNode:
            n.flush()
            binstring = bytes("INITIATOR {}\n".format(init_id), "ascii")
            n.write(binstring)

        # wait before announcing the initiator again
        time.sleep(2)

    logger.info("Script ends")
