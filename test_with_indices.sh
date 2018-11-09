#!/bin/bash

set -ex

#for index in $(seq 6313 6544); do
#for index in $(seq 15 15); do
for index in $(seq $1 $2); do
    # NOTE: Cannot run these in parallel, as they overwrite the
    # tests directory.
    rm -rf tests
    python3 generate_tests.py --test-index $index
    make testbeds LLC=/mnt/revec/build-master-rel-alltarget/bin/llc

    mkdir -p logs
    make run-testbeds > logs/testbeds_index$index.log
done

