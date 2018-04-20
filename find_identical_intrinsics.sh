#!/bin/bash

set -ex

./find_identical_intrinsics.py --log logs/testbeds_seed*.log --output-folder logs/

# Format output JSON
cat logs/test_missed.json | jq "." |& tee logs/test_missed.json > /dev/null
cat logs/test_equivalences.json | jq "." |& tee logs/test_equivalences.json > /dev/null
cat logs/test_conversions.json | jq "." |& tee logs/test_conversions.json > /dev/null
less logs/test_conversions.json

