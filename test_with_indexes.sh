#!/bin/bash

set -ex

for index in $(seq 0 90); do
    # NOTE: Cannot run these in parallel, as they overwrite the
    # tests directory.
    rm -rf tests
    python3 generate_tests.py --test-index $index
    make testbeds

    mkdir -p logs
    make run-testbeds > logs/testbeds_index$index.log
done

