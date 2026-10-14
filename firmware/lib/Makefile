# Host tests for the flight-software libraries. g++ only; no PlatformIO.
# `make test` builds and runs every module that has a test.
CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O1 -Wall -Wextra -g
BUILD    := build

MODULES  := telemetry resetlog ringstore scheduler gpsconfig expframework

.PHONY: all test clean

all: test

test:
	@mkdir -p $(BUILD)
	@fail=0; \
	for m in $(MODULES); do \
	  if [ ! -f $$m/test_$$m.cpp ]; then \
	    echo "SKIP  $$m  (no test_$$m.cpp yet)"; continue; \
	  fi; \
	  echo "== $$m =="; \
	  $(CXX) $(CXXFLAGS) -I. -I. -I$$m -o $(BUILD)/test_$$m $$m/test_$$m.cpp $$m/$$m.cpp \
	    || { echo "FAIL  $$m  (does not build)"; fail=1; continue; }; \
	  ./$(BUILD)/test_$$m || { echo "FAIL  $$m"; fail=1; }; \
	done; \
	if [ $$fail -ne 0 ]; then echo "RESULT: FAILURES"; exit 1; fi; \
	echo "RESULT: all module tests green"

clean:
	rm -rf $(BUILD)
