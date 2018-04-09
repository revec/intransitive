import json

from colorama import Fore, Style

import record_utils

types = {
    "llvm_i32_ty": "i32",
}

def get_type(identifier):
    if identifier in types:
        return types[identifier]

    assert identifier.startswith("llvm_"), "Bad type: {}".format(identifier)
    assert identifier.endswith("_ty"), "Bad type: {}".format(identifier)
    identifier = identifier[5:-3]

    return identifier

def make_testbed(intrinsic, properties, width):
    next_reg = 0

    testbed = """
; ModuleID = 'testbed_{intrinsic}_x{width}'
target datalayout = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

; Function Attrs: nounwind uwtable
define i32 @main() local_unnamed_addr #0 {{
""".format(intrinsic=intrinsic, width=width)

    for i in range(width):
        #%2 = tail call <2 x double> @llvm.x86.sse2.sqrt.pd(<2 x double> <double 0x41E1806340000000, double 0x3FD4C04000000000>)
        out_reg = "out"
        testbed += \
            "  %{out_reg} = call {out_dtype} @{LLVMFunction}(...);\n".format(
                    out_reg=out_reg,
                    out_dtype=get_type(properties["RetTypes"][0]),
                    **properties)

    # TODO: Should the target features +avx,+avx2 be added conditionally?
    testbed += """}

attributes #0 = { nounwind uwtable "target-cpu"="x86-64" "target-features"="+fxsr,+mmx,+sse,+sse2,+x87" }
    """
    return testbed

if __name__=="__main__":
    with open("intrinsics_all.json") as intrinsics_file:
        intrinsics = json.load(intrinsics_file)

        sse2 = record_utils.filter_sse2(intrinsics)
        avx = record_utils.filter_avx(intrinsics)
        avx2 = record_utils.filter_avx2(intrinsics)

        for intrinsic, properties in sse2.items():
            if len(properties["RetTypes"]) == 1 and properties["RetTypes"][0]:
                testbed = make_testbed(intrinsic, properties, width=2)

                print("===============")
                print(intrinsic)
                print(properties)
                print(testbed)
            else:
                print("{Fore.RED}Skipping intrinsic {intrinsic} due to bad return types {RetTypes}{Style.RESET_ALL}\n"\
                      .format(**locals(), RetTypes=properties["RetTypes"]))

