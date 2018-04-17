
intrinsics: intrinsics.cpp
	g++ intrinsics.cpp -g -I${LLVM_BUILD}/include -I${LLVM_SRC}/include -o intrinsics

testbeds:
	find tests -name "testbed.ll" | sort | xargs -I % llc-6.0 % -O0 -mcpu=skylake
	find tests -name "testbed.s" | sort | xargs -I % sh -c "as % --64 -o \"\`dirname %\`/testbed.o\";"
	find tests -name "testbed.o" | sort | xargs -I % sh -c "gcc -m64 % -o \`dirname %\`/testbed;"

run-testbeds:
	find tests -name "testbed" | xargs -I % sh -c "echo 'TEST START %'; ./%; echo 'TEST STOP\n';"

