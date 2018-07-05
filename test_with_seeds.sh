#!/bin/bash

set -ex

for seed in $(seq $1 $2); do
    # NOTE: Cannot run these in parallel, as they overwrite the
    # tests directory.
    rm -rf tests
    python3 generate_tests.py --seed $seed
    make testbeds

    mkdir -p logs
    make run-testbeds > logs/testbeds_seed$seed.log
done

