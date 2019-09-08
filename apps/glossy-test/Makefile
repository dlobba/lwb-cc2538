CONTIKI_PROJECT = glossy_test
CONTIKI_WITH_RIME = 1

DEFINES += PROJECT_CONF_H=\"project-conf.h\"

PROJECTDIRS += ../deployment
PROJECT_SOURCEFILES += deployment.c

LDFLAGS += -specs=nosys.specs
include ../../Makefile.lwb

# pass application macro to the compilation chain
INITIATOR_ID ?= 1
PAYLOAD_LEN  ?= 0
TX_POWER     ?= CC2538_RF_TX_POWER_RECOMMENDED
NTX          ?= 1

CFLAGS += -DINITIATOR_ID=$(INITIATOR_ID)
CFLAGS += -DGLOSSY_TEST_CONF_PAYLOAD_DATA_LEN=$(PAYLOAD_LEN)
CFLAGS += -DCC2538_RF_CONF_TX_POWER=$(TX_POWER)
CFLAGS += -DGLOSSY_TEST_CONF_N_TX=$(NTX)

#  db - code mapping
#  {  7, 0xFF },
#  {  5, 0xED },
#  {  3, 0xD5 },
#  {  1, 0xC5 },
#  {  0, 0xB6 },
#  { -1, 0xB0 },
#  { -3, 0xA1 },
#  { -5, 0x91 },
#  { -7, 0x88 },
#  { -9, 0x72 },
#  {-11, 0x62 },
#  {-13, 0x58 },
#  {-15, 0x42 },
#  {-24, 0x00 },

all: $(CONTIKI_PROJECT)
CONTIKI = ../../contiki
include $(CONTIKI)/Makefile.include

