/*
 * Copyright (c) 2016, Uppsala University, Sweden.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * 3. Neither the name of the copyright holder nor the names of its
 *    contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 * FOR A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE
 * COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 * (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
 * STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
 * OF THE POSSIBILITY OF SUCH DAMAGE.
 *
 * Author:  Kasun Hewage
 *
 */

#include <stdio.h>
#include <inttypes.h>
#include <stdbool.h>

#include "dev/leds.h"

#include "sys/autostart.h"
#include "sys/rtimer.h"
#include "sys/etimer.h"

#include "glossy.h"
#include "deployment.h"
/*---------------------------------------------------------------------------*/
#define XSTR(x) #x
#define STR(x) XSTR(x)
/*---------------------------------------------------------------------------*/
#ifndef INITIATOR_ID
#error No initiator id given. Define the INITIATOR_ID macro
#endif /* INITIATOR_ID */
/*---------------------------------------------------------------------------*/
#define GLOSSY_PERIOD                   (RTIMER_SECOND / 4)      /* 250 milliseconds */
//#define GLOSSY_T_SLOT                   (RTIMER_SECOND / 33)        /* 30 ms*/
#define GLOSSY_T_SLOT                   (RTIMER_SECOND / 50)       /* 20 ms*/
#define GLOSSY_T_GUARD                  (RTIMER_SECOND / 1000)     /* 1ms */
#ifdef GLOSSY_TEST_CONF_N_TX
#define GLOSSY_N_TX                     GLOSSY_TEST_CONF_N_TX
#else
#define GLOSSY_N_TX                     2
#endif
/*---------------------------------------------------------------------------*/
#ifdef GLOSSY_TEST_CONF_PAYLOAD_DATA_LEN
#define PAYLOAD_DATA_LEN                GLOSSY_TEST_CONF_PAYLOAD_DATA_LEN
#else
#define PAYLOAD_DATA_LEN                109
#endif
/*---------------------------------------------------------------------------*/
/*                          PRINT MACRO DEFINITIONS                          */
/*---------------------------------------------------------------------------*/
#pragma message ("INITIATOR_ID:             "   STR( INITIATOR_ID ))
#pragma message ("PAYLOAD_DATA_LEN:         "   STR( PAYLOAD_DATA_LEN ))
#pragma message ("GLOSSY_N_TX:              "   STR( GLOSSY_N_TX ))
#pragma message ("GLOSSY_PERIOD:            "   STR( GLOSSY_PERIOD ))
#pragma message ("GLOSSY_SLOT:              "   STR( GLOSSY_T_SLOT ))
#pragma message ("GLOSSY_GUARD:             "   STR( GLOSSY_T_GUARD ))
/*---------------------------------------------------------------------------*/
#define WAIT_UNTIL(time) \
{\
    rtimer_set(&g_timer, (time), 0, (rtimer_callback_t)glossy_thread, rt);\
    PT_YIELD(&glossy_pt);\
}
/*---------------------------------------------------------------------------*/
typedef struct {
    uint32_t seq_no;
    uint8_t  data[PAYLOAD_DATA_LEN];
}
__attribute__((packed))
glossy_data_t;
/*---------------------------------------------------------------------------*/
static struct pt      glossy_pt;
static struct rtimer  g_timer;
static glossy_data_t  glossy_payload;
static glossy_data_t  previous_payload;
static uint8_t        bootstrapped = 0;
static uint16_t       bootstrap_cnt = 0;
static uint16_t       pkt_cnt = 0;
static uint16_t       miss_cnt = 0;

static rtimer_clock_t previous_t_ref;
static rtimer_clock_t t_ref;

/*---------------------------------------------------------------------------*/
// Contiki Process definition
PROCESS(glossy_test, "Glossy test");
AUTOSTART_PROCESSES(&glossy_test);
/*---------------------------------------------------------------------------*/
static unsigned short int initiator_id = INITIATOR_ID;
static uint8_t password[]   = {0x0, 0x0, 0x4, 0x2};
static size_t  password_len = 0;
static bool    password_set = false;
/*---------------------------------------------------------------------------*/
static bool password_check(
        const uint8_t *payload_data, const size_t payload_len,
        const uint8_t *password, const size_t password_len);
/*---------------------------------------------------------------------------*/
PT_THREAD(glossy_thread(struct rtimer *rt))
{

    PT_BEGIN(&glossy_pt);

    printf("Starting Glossy. Node ID %hu\n", node_id);

    previous_t_ref     = 0;

    while (1) {

        if(node_id == initiator_id) {

            glossy_start(node_id,
                    (uint8_t*)&glossy_payload,
                    sizeof(glossy_data_t),
                    GLOSSY_N_TX,
                    GLOSSY_WITH_SYNC);

            WAIT_UNTIL(rt->time + GLOSSY_T_SLOT);
            glossy_stop();

            printf("[GLOSSY_BROADCAST]sent_seq %"PRIu32", payload_len %u\n",
                    glossy_payload.seq_no,
                    sizeof(glossy_data_t));
            printf("[GLOSSY_PAYLOAD]rcvd_seq %"PRIu32"\n", glossy_payload.seq_no);
            printf("[APP_STATS]n_rx %"PRIu8", n_tx %"PRIu8", f_relay_cnt %"PRIu8", "
                    "rcvd %"PRIu16", missed %"PRIu16", bootpd %"PRIu16"\n",
                    glossy_get_n_rx(), glossy_get_n_tx(),
                    glossy_get_relay_cnt_first_rx(),
                    pkt_cnt,
                    miss_cnt,
                    bootstrap_cnt);

            glossy_debug_print();
            glossy_stats_print();

            if (previous_payload.seq_no > 0 &&
                    glossy_payload.seq_no == previous_payload.seq_no + 1) {

                printf("[APP_DEBUG]Epoch_diff rtimer %"PRIu32"\n",
                        glossy_get_t_ref() - previous_t_ref);

            }

            previous_t_ref = glossy_get_t_ref();
            previous_payload = glossy_payload;

            glossy_payload.seq_no++;

            WAIT_UNTIL(rt->time - GLOSSY_T_SLOT + GLOSSY_PERIOD);

        } else { /* --------------------------------------------- receiver -- */

            if(!bootstrapped) {
                printf("BOOTSTRAP\r\n");
                bootstrap_cnt++;
                do {
                    glossy_start(GLOSSY_UNKNOWN_INITIATOR, (uint8_t*)&glossy_payload,
                            GLOSSY_UNKNOWN_PAYLOAD_LEN,
                            GLOSSY_N_TX, GLOSSY_WITH_SYNC);
                    WAIT_UNTIL(rt->time + GLOSSY_T_SLOT);
                    glossy_stop();
                } while(!glossy_is_t_ref_updated());
                /* synchronized! */
                bootstrapped = 1;
            } else {
                /* already synchronized, receive a packet */
                glossy_start(GLOSSY_UNKNOWN_INITIATOR, (uint8_t*)&glossy_payload,
                        GLOSSY_UNKNOWN_PAYLOAD_LEN,
                        GLOSSY_N_TX, GLOSSY_WITH_SYNC);
                WAIT_UNTIL(rt->time + GLOSSY_T_SLOT + GLOSSY_T_GUARD);
                glossy_stop();
            }

            /* has the reference time been updated? */
            if(glossy_is_t_ref_updated()) {
                /* sync received */
                printf("[APP_DEBUG]Synced\n");
                t_ref = glossy_get_t_ref() + GLOSSY_PERIOD;
            } else {
                /* sync missed */
                printf("[APP_DEBUG]Not Synced\n");
                t_ref += GLOSSY_PERIOD;
            }

            /* at least one packet received? */
            if(glossy_get_n_rx()) {
                pkt_cnt++;
                /*---------------------------------------------------------------*/
                // Check packet integrity
                /*---------------------------------------------------------------*/
                if (password_set && !password_check(glossy_payload.data, PAYLOAD_DATA_LEN,
                            password, password_len)) {

                    printf("[APP_DEBUG]Received a corrupted packet.\n");

                } else {

                    printf("[GLOSSY_PAYLOAD]rcvd_seq %"PRIu32"\n", glossy_payload.seq_no);
                    printf("[APP_STATS]n_rx %"PRIu8", n_tx %"PRIu8", f_relay_cnt %"PRIu8", "
                            "rcvd %"PRIu16", missed %"PRIu16", bootpd %"PRIu16"\n",
                            glossy_get_n_rx(), glossy_get_n_tx(),
                            glossy_get_relay_cnt_first_rx(),
                            pkt_cnt,
                            miss_cnt,
                            bootstrap_cnt);

                    // print info to compute stats
                    glossy_debug_print();
                    glossy_stats_print();

                    // print difference between the reference time among two
                    // consecutive packets, ignore the first packet
                    if (previous_payload.seq_no > 0 &&
                        glossy_payload.seq_no == previous_payload.seq_no + 1) {

                        printf("[APP_DEBUG]Epoch_diff rtimer %"PRIu32"\n",
                                glossy_get_t_ref() - previous_t_ref);

                    }
                    previous_t_ref = glossy_get_t_ref();

                    previous_payload = glossy_payload;

                }
            }
            else { /* no packet received */
                miss_cnt++;
            }

            /*---------------------------------------------------------------*/

            WAIT_UNTIL(t_ref - GLOSSY_T_GUARD);

        }
    }
    PT_END(&glossy_pt);
}
/*---------------------------------------------------------------------------*/

PROCESS_THREAD(glossy_test, ev, data)
{
    PROCESS_BEGIN();


    deployment_load_ieee_addr();
    deployment_set_node_id_ieee_addr();

    if (glossy_init() == GLOSSY_STATUS_FAIL) {
        printf("Glossy init failed\n");
        PROCESS_EXIT();
    }

    printf("Glossy successfully initialised\n");

    // DON'T SET ENCODING
    glossy_set_enc(GLOSSY_ENC_OFF);

    // Add a password to the data payload to check for packet integrity
    glossy_payload.seq_no  = 0;
    password_len = sizeof(password) / sizeof(password_len);
    if (password_len > PAYLOAD_DATA_LEN) {
        printf("Password too large to be embedded within the app payload!\n");
        printf("Password not set!\n");
        password_set = false;
    } else {
        memcpy(glossy_payload.data, password, password_len * sizeof(uint8_t));
        password_set = true;
    }
    previous_payload = glossy_payload;

    /*-----------------------------------------------------------------------*/
    // make the initiator wait a bit longer
    if(node_id == initiator_id) {
        rtimer_set(&g_timer, RTIMER_NOW() + RTIMER_SECOND * 10, 0,
                (rtimer_callback_t)glossy_thread, NULL);
    } else {
        rtimer_set(&g_timer, RTIMER_NOW() + RTIMER_SECOND * 2, 0,
                (rtimer_callback_t)glossy_thread, NULL);
    }
    /*-----------------------------------------------------------------------*/
    PROCESS_END();
}
/*---------------------------------------------------------------------------*/
static bool
password_check(const uint8_t *payload_data, const size_t payload_len,
        const uint8_t *password, const size_t password_len)
{
    size_t i = 0;
    if (payload_len < password_len) {
        return false;
    }
    for (; i < password_len; i++) {
        if (payload_data[i] != password[i]) {
            return false;
        }
    }
    return true;
}
