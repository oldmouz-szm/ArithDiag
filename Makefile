PYTHON ?= python3
.PHONY: all test
all:
	$(MAKE) -C baseline/native
	$(MAKE) -C native/ls-iqcqp
test: all
	$(PYTHON) -B tests/check_correctness.py
	$(PYTHON) -B tests/check_native.py
