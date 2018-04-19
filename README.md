# LLVM Intrinsic Translation

Generate peephole rules to collapse intrinsics in LLVM IR, particularly for vector intrinsics.

Example generation process:
```
export ENUM_SEED=02139
rm -r tests
python3 generate_tests.py --seed $ENUM_SEED
make testbeds
make run-testbeds > testbeds_seed$ENUM_SEED.log
```
