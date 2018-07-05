#include "llvm/IR/Attributes.h"
#include "llvm/IR/Intrinsics.h"
#include "llvm/Support/ErrorHandling.h"


#include <iostream>
#include <string>

using namespace std;
using namespace llvm;

/// Table of string intrinsic names indexed by enum value.
static const char * const IntrinsicNameTable[] = {
  "not_intrinsic",
#define GET_INTRINSIC_NAME_TABLE
#include "llvm/IR/Intrinsics.gen"
#undef GET_INTRINSIC_NAME_TABLE
};

#if 0
/// Table of per-target intrinsic name tables.
#define GET_INTRINSIC_TARGET_DATA
#include "llvm/IR/Intrinsics.gen"
#undef GET_INTRINSIC_TARGET_DATA

/// Query attributes by Intrinsic ID.
#define GET_INTRINSIC_ATTRIBUTES
#include "llvm/IR/Intrinsics.gen"
#undef GET_INTRINSIC_ATTRIBUTES
#endif

bool startswith(const string& base, const string& prefix) {
    return base.substr(0, prefix.size()) == prefix;
}

int main() {
    int num_intrinsics = sizeof(IntrinsicNameTable) / sizeof(char *);

    for (int ID = 0; ID < num_intrinsics; ID++) {
        const string& name = IntrinsicNameTable[ID];

        if (startswith(name, "llvm.x86.avx2")) {
            std::cout << name << std::endl;
        }
    }
    return 0;
}
