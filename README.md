# LLVM Intrinsic Translation

Generate peephole rules to collapse intrinsics in LLVM IR, particularly for vector intrinsics.

## Generation process:
```
# Set up virtual environment
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt

# Generate intrinsics_all.json from IntrinsicRecords.td (TableGen file from LLVM source)
python parse_records.py

# Test all intrinsics through a range of repetitions for different seeds / edge cases
./test_with_seeds.sh 0 6500
./test_with_indexes.sh

# Parse test run log output (stored in logs/) and filter to find equivalent intrinsics
./find_identical_intrinsics.sh

# Generate a header file that encodes discovered equivalences
python generate_intrinsic_map.py
```

## Old instructions (for a single seed)
```
export ENUM_SEED=02139
rm -r tests
python3 generate_tests.py --seed $ENUM_SEED
make testbeds
make run-testbeds > testbeds_seed$ENUM_SEED.log
python3 generate_intrinsic_map.py
```
