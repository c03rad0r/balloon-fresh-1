# Convenience targets for the FIPS over LR2021 reference.
# Override FIPS_DIR to use an existing checkout.

FIPS_DIR ?= $(CURDIR)/build/fips
PROBE ?=

.PHONY: all bootstrap host-test mock-e2e build-fips build-e80 flash-e80 clean

all: host-test mock-e2e build-e80

bootstrap:
	FIPS_DIR=$(FIPS_DIR) ./scripts/bootstrap-fips.sh

host-test:
	FIPS_DIR=$(FIPS_DIR) ./scripts/test-host.sh

mock-e2e:
	FIPS_DIR=$(FIPS_DIR) ./tests/host/run_mock_e2e.sh

build-fips:
	FIPS_DIR=$(FIPS_DIR) ./scripts/build.sh

build-e80:
	./scripts/build-e80-bridge.sh

flash-e80:
	PROBE=$(PROBE) ./scripts/flash-e80-bridge.sh

clean:
	rm -rf build firmware/rp2040-bridge/.pio
