
intrinsics: intrinsics.cpp
	clang++-6.0 intrinsics.cpp -g -I${LLVM_BUILD}/include -I${LLVM_SRC}/include -o intrinsics

testbeds:
	find tests -name "testbed.ll" | sort | xargs -n 1 -P `nproc` -I % llc-6.0 % -O0 -mcpu=skylake-avx512
	find tests -name "testbed.s"  | sort | xargs -n 1 -P `nproc` -I % sh -c "as % --64 -o \"\`dirname %\`/testbed.o\";"
	find tests -name "testbed.o"  | sort | xargs -n 1 -P `nproc` -I % sh -c "gcc -m64 % -o \`dirname %\`/testbed || true;"

run-testbeds:
	find tests -name "testbed" | xargs -I % sh -c "echo 'TEST START %'; ./%; echo 'TEST STOP\n';"

