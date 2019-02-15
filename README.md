# Intransitive: Discovering intrinsic translations

Generate rules to collapse sequences of LLVM vector IR intrinsics into shorter sequences of equivalent (wider) operations. This is done via testbed generation, randomized testing of input bit sequences, and testing with combinatorially generated corner-case bit sequences.

We tested 18,000 such inputs on an Intel Skylake Xeon processor with AVX-512 support. In our tests, Intransitive discovered 53 SSE-series to AVX1/2 intrinsic conversions, 33 AVX1/2 to AVX-512 conversions, and 19 SSE-series to AVX-512 conversions. For instance, the SSE4.1 intrinsic `_mm_packus_epi32` has a 2-to-1 conversion to `_mm256_packus_epi32` and a 4-to-1 conversion to `_mm512_packus_epi32`.

See [Revec: Program Rejuventation through Revectorization](https://arxiv.org/pdf/1902.02816.pdf) for details on the equivalence generation process.

## Generation process:
### Set up a virtual environment
```
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### Enumeration process
```
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

### Updating IntrinsicRecords.td
If needed, IntrinsicRecords.td can be regenerated from intrinsic definitions in the LLVM source. This is necessary when intrinsic definitions in the LLVM source change -- particularly when `include/llvm/IR/Intrinsics.td` or `include/llvm/IR/IntrinsicsX86.td` change. From the root of the LLVM source repository (e.g. a clone of https://github.com/llvm-mirror/llvm), execute:
```
llvm-tblgen include/llvm/IR/Intrinsics.td -Iinclude > /path/to/output/IntrinsicRecords.td
```

For example,
```
/mnt/revec/build-master/bin/llvm-tblgen include/llvm/IR/Intrinsics.td -Iinclude > ../enum/IntrinsicRecords.td
```

This repository currently contains definitions generated from LLVM's `release_60` branch.
