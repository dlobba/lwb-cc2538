CONTIKI_PROJECT = glossy_test
CONTIKI_WITH_RIME = 1

DEFINES += PROJECT_CONF_H=\"project-conf.h\"

PROJECTDIRS += ../deployment
PROJECT_SOURCEFILES += deployment.c

LDFLAGS += -specs=nosys.specs
include ../../Makefile.lwb

# pass application macro to the compilation chain
INITIATOR_ID=
PAYLOAD_LEN=
TX_POWER=
ifneq ($(strip $(INITIATOR_ID)),)
	CFLAGS += -DINITIATOR_ID=$(INITIATOR_ID)
endif

ifneq ($(strip $(PAYLOAD_LEN)),)
	CFLAGS += -DGLOSSY_TEST_CONF_PAYLOAD_DATA_LEN=$(PAYLOAD_LEN)
endif

ifneq ($(strip $(TX_POWER)),)
	CFLAGS += -DCC2538_RF_CONF_TX_POWER=$(TX_POWER)
endif

all: $(CONTIKI_PROJECT)
CONTIKI = ../../contiki
include $(CONTIKI)/Makefile.include

