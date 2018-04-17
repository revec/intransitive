import argparse
import binascii
import json
import os
import random
import re
import struct
import sys
import time

from colorama import Fore, Style

import record_utils

parser = argparse.ArgumentParser(description="Generate testbeds for intrinsic equality testing")
parser.add_argument("--seed", type=int, required=True,
                    help="Seed for the input generator")
parser.add_argument("--max-bits", type=int, default=768,
                    help="Maximum number of bits to generate for inputs")
#parser.add_argument("--shuffle-input", type=int, default=0x000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F02122232425262728292A2B2C2D2E2F303132333435363738393A3B3C3D3E3F404142434445464748494A4B4C4D4E4F505152535455565758595A5B5C5D5E5F)
args = parser.parse_args()

type_to_format = {
    "i8": "b", # signed char
    "i16": "h",
    "i32": "i",
    "i64": "q",
}

def get_type(identifier):
    m = re.match(r"llvm_v([0-9]+)([if])([0-9]+)_ty", identifier)
    if m:
        # Vector type
        width = int(m.group(1))
        element_i_f = m.group(2)
        element_bits = int(m.group(3))

        element_type = "{}{}".format(element_i_f, element_bits)
        if element_type == "f64":
            element_type = "double"
        elif element_type == "f32":
            element_type = "float"

        return "<{width} x {element_type}>".format(**locals()), width, element_type, element_bits

    m = re.match(r"llvm_([if])([0-9]+)_ty", identifier)
    if m:
        # Scalar type
        ty = m.group(1) + m.group(2)
        return ty, 1, m.group(1), int(m.group(2))

    raise TypeError(Fore.RED + "Bad type: {}".format(identifier) + Style.RESET_ALL)

def random_bytes(num_bytes, seed):
    random.seed(seed)

    value = 0
    for i in range(num_bytes):
        byte = random.randint(0, 255)
        value = value << 8
        value = value | byte

    return value

def left_pad(base, target_length, pad_char):
    while len(base) < target_length:
        base = pad_char + base
    return base

def make_testbed(intrinsic, properties, num_repeat, n_input_bits, inputs):
    """Return a string for a LLVM IR program that tests the provided intrinsic on inputs"""

    # Properties and state
    out_dtype, out_width, _, out_element_bits  = get_type(properties["RetTypes"][0])
    out_bitwidth = out_width * out_element_bits
    out_alignment = out_bitwidth // 8
    next_register = 1

    # Header and method signature
    testbed = """
; ModuleID = 'testbed_{intrinsic}_repeat{num_repeat}'
target triple = "x86_64-pc-linux-gnu"
target datalayout = ""

; Function Attrs: nounwind uwtable
define i32 @main() local_unnamed_addr {{
""".format(intrinsic=intrinsic, num_repeat=num_repeat)

    # Allocate memory for outputs
    out_mem_ptrs = []
    for i in range(num_repeat):
        out_mem_ptrs.append(next_register)
        testbed += "  %{} = alloca {}, align {}\n".format(
                next_register, out_dtype, out_alignment)
        next_register += 1

    for i in range(num_repeat):
        params = []
        for param_type_id in properties["ParamTypes"]:
            param_type, param_width, param_element_type, param_element_bits = get_type(param_type_id)

            constants = []
            for j in range(param_width):
                mask = (1 << param_element_bits) - 1
                constant = inputs & mask
                inputs = inputs >> param_element_bits

                const_hex = hex(constant)[2:]
                if len(const_hex) % 2 == 1:
                    const_hex = left_pad(const_hex, len(const_hex) + 1, "0")
                const_bytes = bytes.fromhex(const_hex)
                const_bytes = left_pad(const_bytes, param_element_bits // 8, b"0")

                if param_element_type == "double":
                    constants.append("{} 0x{}".format(param_element_type, const_hex))
                elif param_element_type == "float":
                    const_float = struct.unpack('f', const_bytes)[0]
                    const_double_bytes = struct.pack('>d', const_float)
                    const_double_hex = const_double_bytes.hex()
                    constants.append("{} 0x{}".format(param_element_type, const_double_hex))
                elif param_element_type[0] == "i":
                    format_string = type_to_format[param_element_type]
                    const_value = struct.unpack(format_string, const_bytes)[0]
                    constants.append("{} {}".format(param_element_type, const_value))
                else:
                    raise TypeError("Invalid element type {} for parameter of type: {}".format(param_element_type, param_type))

            params.append("{} <{}>".format(param_type, ", ".join(constants)))
        param_string = ", ".join(params)

        testbed += \
            "  %{next_register} = call {out_dtype} @{LLVMFunction}({params})\n".format(
                    next_register=next_register,
                    out_dtype=out_dtype,
                    params=param_string,
                    **properties)
        next_register += 1

        testbed += "  store {dtype} %{out_reg}, {dtype}* %{out_mem_ptr}, align {align}\n".format(
                dtype=out_dtype,
                out_reg=next_register - 1,
                out_mem_ptr=out_mem_ptrs[i],
                align=out_alignment)

    for i in range(num_repeat):
        testbed += "  %{} = bitcast {}* %{} to i8*\n".format(
                next_register, out_dtype, out_mem_ptrs[i])
        next_register += 1

        testbed += "  call void @print_bytes(i8* %{}, i64 {})\n".format(
                next_register - 1, out_alignment)

    testbed += "  ret i32 0\n"
    testbed += "}"

    # Declare stubs for intrinsics, printing
    params = []
    for param_type_id in properties["ParamTypes"]:
        param_type, param_width, param_element_type, param_element_bits = get_type(param_type_id)
        params.append(param_type)
    param_string = ", ".join(params)
    testbed += """\n
@.str = private unnamed_addr constant [5 x i8] c"%02x\00", align 1

; Function Attrs: noinline nounwind uwtable
define void @print_bytes(i8* nocapture readonly, i64) local_unnamed_addr #0 {{
  %3 = icmp eq i64 %1, 0
  br i1 %3, label %13, label %4
; <label>:4:                                      ; preds = %2
  br label %5
; <label>:5:                                      ; preds = %4, %5
  %6 = phi i64 [ %11, %5 ], [ 0, %4 ]
  %7 = getelementptr inbounds i8, i8* %0, i64 %6
  %8 = load i8, i8* %7, align 1, !tbaa !2
  %9 = zext i8 %8 to i32
  %10 = tail call i32 (i8*, ...) @printf(i8* getelementptr inbounds ([5 x i8], [5 x i8]* @.str, i64 0, i64 0), i32 %9)
  %11 = add nuw i64 %6, 1
  %12 = icmp eq i64 %11, %1
  br i1 %12, label %13, label %5
; <label>:13:                                     ; preds = %5, %2
  %14 = tail call i32 @putchar(i32 10)
  ret void
}}

; Function Attrs: nounwind
declare i32 @printf(i8* nocapture readonly, ...) local_unnamed_addr #1

; Function Attrs: nounwind
declare i32 @putchar(i32) local_unnamed_addr #2

; Function Attrs: nounwind readnone
declare {rtype} @{intrinsic}({ptypes}) #3

attributes #0 = {{ noinline nounwind uwtable }}
attributes #1 = {{ argmemonly nounwind }}
attributes #2 = {{ nounwind }}
attributes #3 = {{ nounwind readnone }}

!2 = !{{!3, !3, i64 0}}
!3 = !{{!"omnipotent char", !4, i64 0}}
!4 = !{{!"Simple C/C++ TBAA"}}""".format(
        rtype=out_dtype,
        intrinsic=properties["LLVMFunction"],
        ptypes=param_string)

    return testbed

def generate_store_testbed(intrinsic, properties, n_input_bits, inputs):
    """Generate and store a testbed"""
    if not (len(properties["RetTypes"]) == 1 and properties["RetTypes"][0]):
        print("{}Skipping intrinsic {} due to bad return types {}{}"\
              .format(Fore.YELLOW, intrinsic, properties["RetTypes"], Style.RESET_ALL),
              file=sys.stderr)
        return

    # Find the max bitwidth of return and param types
    #_, ret_width, __, ret_element_bits = get_type(properties["RetTypes"])
    #max_bits = ret_width * ret_element_bits

    total_param_bits = 0
    for param_type in properties["ParamTypes"]:
        if not re.match("llvm_v[0-9]+", param_type):
            print("{}Skipping intrinsic {} due to non-vector param type {}{}"\
                  .format(Fore.RED, intrinsic, properties["ParamTypes"], Style.RESET_ALL),
                  file=sys.stderr)
            return

        _, param_width, __, param_element_bits = get_type(param_type)
        total_param_bits += param_width * param_element_bits

    # Find how many times to repeat the operation
    max_num_repeat = n_input_bits // total_param_bits

    for num_repeat in range(1, max_num_repeat + 1):
        testbed = make_testbed(
                    intrinsic, properties, num_repeat, n_input_bits, inputs)

        print("===============")
        print(intrinsic)
        print(properties)

        intrinsic_folder = os.path.join("tests", intrinsic, "repeat_{}".format(num_repeat))
        os.makedirs(intrinsic_folder, exist_ok=True)

        with open(os.path.join(intrinsic_folder, "properties.json"), "w") as properties_file:
            json.dump(properties, properties_file)

        with open(os.path.join(intrinsic_folder, "testbed.ll"), "w") as testbed_file:
            testbed_file.write(testbed)

if __name__=="__main__":
    intel_vector = {}

    with open("intrinsics_all.json") as intrinsics_file:
        intrinsics = json.load(intrinsics_file)
        intel_vector = record_utils.filter_intel_vector(intrinsics)

    inputs = random_bytes(args.max_bits // 8, args.seed)

    for intrinsic in sorted(intel_vector.keys()):
        properties = intel_vector[intrinsic]
        generate_store_testbed(intrinsic, properties, args.max_bits, inputs)

    # TODO: Compile testbeds with llc


