#!/bin/bash

llvm-tblgen $LLVM_SRC/include/llvm/IR/Intrinsics.td -print-records > IntrinsicRecords.gen
