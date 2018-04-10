import json
import re

from colorama import Fore, Style

import record_utils

def get_type(identifier):
    m = re.match(r"llvm_v([0-9]+)([if])([0-9]+)_ty", identifier)
    if m:
        width = int(m.group(1))
        element_type = m.group(2)
        element_bits = int(m.group(3))

        return "<{width} x {element_type}{element_bits}>".format(**locals())

    m = re.match(r"llvm_([if][0-9]+)_ty", identifier)
    if m:
        return m.group(1)

    raise TypeError(Fore.RED + "Bad type: {}".format(identifier) + Style.RESET_ALL)

def make_testbed(intrinsic, properties, width):
    next_reg = 0

    testbed = """
; ModuleID = 'testbed_{intrinsic}_x{width}'
target triple = "x86_64-pc-linux-gnu"
target datalayout = ""

; Function Attrs: nounwind uwtable
define i32 @main() local_unnamed_addr {{
""".format(intrinsic=intrinsic, width=width)

    next_register = 1

    for i in range(width):
        #%2 = tail call <2 x double> @llvm.x86.sse2.sqrt.pd(<2 x double> <double 0x41E1806340000000, double 0x3FD4C04000000000>)
        out_reg = "out"
        testbed += \
            "  %{next_register} = call {out_dtype} @{LLVMFunction}(...);\n".format(
                    next_register=next_register,
                    out_reg=out_reg,
                    out_dtype=get_type(properties["RetTypes"][0]),
                    **properties)
        next_register += 1

    testbed += "}"
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

