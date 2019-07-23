CONTIKI_PROJECT = glossy_test
CONTIKI_WITH_RIME = 1

DEFINES += PROJECT_CONF_H=\"project-conf.h\"

PROJECTDIRS += ../deployment
PROJECT_SOURCEFILES += deployment.c

LDFLAGS += -specs=nosys.specs
include ../../Makefile.lwb

all: $(CONTIKI_PROJECT)
CONTIKI = ../../contiki
include $(CONTIKI)/Makefile.include

