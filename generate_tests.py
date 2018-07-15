#!/usr/bin/env python3

import argparse
import enum
import itertools
import json
import math
import os
import random
import re
import struct
import sys
import time
import traceback

from colorama import Fore, Style

import record_utils
from utilities import Combination, get_type, type_to_format

parser = argparse.ArgumentParser(description="Generate testbeds for intrinsic equality testing")
parser.add_argument("--seed", type=int, required=False, default=0,
                    help="Seed for the input generator. The default of 0 indicates that edge cases should be generated.")
parser.add_argument("--test-index", type=int, required=False, default=0,
                    help="Index of generated test (made of specific byte chunks)")
parser.add_argument("--max-bits", type=int, default=2048,
                    help="Maximum number of bits to generate for inputs")
#parser.add_argument("--shuffle-input", type=int, default=0x000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F02122232425262728292A2B2C2D2E2F303132333435363738393A3B3C3D3E3F404142434445464748494A4B4C4D4E4F505152535455565758595A5B5C5D5E5F)
args = parser.parse_args()

test_byte_chunks = [
    "00" * 8,
    "10" * 8,
    "01" * 8,
    "ff" * 8,
]

def combine_test_input_chunks(num_bytes, test_index):
    """Generate a test"""
    combinations = list(itertools.combinations_with_replacement(test_byte_chunks, num_bytes // 8))
    print("Number of test inputs possible: {}".format(len(combinations)))

    for i, chunks in enumerate(combinations):
        if i == test_index:
            hex_string = "".join(chunks)
            return int(hex_string, 16)

    raise IndexError("Test index {} out of range (range: 0-{})".format(test_index, i))

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

def make_testbed(intrinsic, properties, n_input_bits, inputs, num_repeat, combination):
    """Return a string for a LLVM IR program that tests the provided intrinsic on inputs"""

    # Properties and state
    out_dtype, out_width, _, out_element_bits  = get_type(properties["RetTypes"][0])
    out_bitwidth = out_width * out_element_bits
    out_alignment = out_bitwidth // 8
    next_register = 1

    # Header and method signature
    main_body = ""

    # Allocate memory for outputs
    out_mem_ptrs = []
    for i in range(num_repeat):
        out_mem_ptrs.append(next_register)
        main_body += "  %{} = alloca {}, align {}\n".format(
                next_register, out_dtype, out_alignment)
        next_register += 1

    # Make a num_repeat x num_params constant table
    num_params = len(properties["ParamTypes"])
    param_constants = [[0 for j in range(num_params)]
                    for i in range(num_repeat)]

    if combination == Combination.VERTICAL:
        # Populate the constants table column first.
        # That is, assign the first parameter of each instruction first, then the
        # second of each, etc.
        for j in range(num_params):
            param_type_id = properties["ParamTypes"][j]
            param_type, param_width, param_element_type, param_element_bits = get_type(param_type_id)
            param_total_bits = param_width * param_element_bits

            for i in range(num_repeat):
                # Grab enough bits from the input for this vector parameter
                mask = (1 << param_total_bits) - 1
                constant = inputs & mask
                inputs = inputs >> param_total_bits
                param_constants[i][j] = (param_type_id, constant)
    elif combination == Combination.HORIZONTAL:
        # Populate the constants table row first.
        # That is, assign all the parameters of the first instruction first, then all the parameters of the second, etc.
        for i in range(num_repeat):
            for j in range(num_params):
                param_type_id = properties["ParamTypes"][j]
                param_type, param_width, param_element_type, param_element_bits = get_type(param_type_id)
                param_total_bits = param_width * param_element_bits

                # Grab enough bits from the input for this vector parameter
                mask = (1 << param_total_bits) - 1
                constant = inputs & mask
                inputs = inputs >> param_total_bits
                param_constants[i][j] = (param_type_id, constant)

    # Using these input constants, build the instruction
    for i in range(num_repeat):
        params = []

        for param_type_id, param_constant in param_constants[i]:
            param_type, param_width, param_element_type, param_element_bits = get_type(param_type_id)

            element_constants = []
            # Split the input constant into chunks for each element of the parameter vector
            for j in range(param_width):
                element_mask = (1 << param_element_bits) - 1
                element_constant = param_constant & element_mask
                param_constant = param_constant >> param_element_bits

                const_hex = hex(element_constant)[2:]
                if len(const_hex) % 2 == 1:
                    const_hex = left_pad(const_hex, len(const_hex) + 1, "0")
                const_bytes = bytes.fromhex(const_hex)
                const_bytes = left_pad(const_bytes, param_element_bits // 8, b"0")

                if param_element_type == "double":
                    element_constants.append("{} 0x{}".format(param_element_type, const_hex))
                elif param_element_type == "float":
                    const_float = struct.unpack('f', const_bytes)[0]
                    const_double_bytes = struct.pack('>d', const_float)
                    const_double_hex = const_double_bytes.hex()
                    element_constants.append("{} 0x{}".format(param_element_type, const_double_hex))
                elif param_element_type[0] == "i":
                    format_string = type_to_format[param_element_type]
                    const_value = struct.unpack(format_string, const_bytes)[0]
                    element_constants.append("{} {}".format(param_element_type, const_value))
                else:
                    raise TypeError("Invalid element type {} for parameter of type: {}".format(param_element_type, param_type))

            params.append("{} <{}>".format(param_type, ", ".join(element_constants)))
        param_string = ", ".join(params)

        main_body += \
            "  %{next_register} = call {out_dtype} @{LLVMFunction}({params})\n".format(
                    next_register=next_register,
                    out_dtype=out_dtype,
                    params=param_string,
                    **properties)
        next_register += 1

        main_body += "  store {dtype} %{out_reg}, {dtype}* %{out_mem_ptr}, align {align}\n".format(
                dtype=out_dtype,
                out_reg=next_register - 1,
                out_mem_ptr=out_mem_ptrs[i],
                align=out_alignment)

    for i in range(num_repeat):
        main_body += "  %{} = bitcast {}* %{} to i8*\n".format(
                next_register, out_dtype, out_mem_ptrs[i])
        next_register += 1

        main_body += "  call void @print_bytes(i8* %{}, i64 {})\n".format(
                next_register - 1, out_alignment)

    main_body += "  ret i32 0\n"

    # Declare stubs for intrinsics, printing
    params = []
    for param_type_id in properties["ParamTypes"]:
        param_type, param_width, param_element_type, param_element_bits = get_type(param_type_id)
        params.append(param_type)
    param_string = ", ".join(params)
    testbed = """; ModuleID = 'testbed_{param_intrinsic}_combo{combination}_repeat{num_repeat}'
target triple = "x86_64-pc-linux-gnu"
target datalayout = ""

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

; Function Attrs: nounwind
declare {rtype} @{intrinsic}({ptypes}) local_unnamed_addr #3

; Function Attrs: nounwind uwtable
define i32 @main() local_unnamed_addr {{
{main_body}
}}

attributes #0 = {{ noinline nounwind uwtable }}
attributes #1 = {{ argmemonly nounwind }}
attributes #2 = {{ nounwind }}
attributes #3 = {{ nounwind readnone }}

!2 = !{{!3, !3, i64 0}}
!3 = !{{!"omnipotent char", !4, i64 0}}
!4 = !{{!"Simple C/C++ TBAA"}}""".format(
        param_intrinsic=intrinsic,
        combination=combination.name,
        num_repeat=num_repeat,
        main_body=main_body,
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
    max_log_repeat = int(math.log2(n_input_bits / total_param_bits))

    for log_num_repeat in range(0, max_log_repeat + 1):
        num_repeat = 2 ** log_num_repeat

        for combination in (Combination.HORIZONTAL, Combination.VERTICAL):
            try:
                testbed = make_testbed(
                            intrinsic, properties, n_input_bits, inputs,
                            num_repeat=num_repeat,
                            combination=combination)

                intrinsic_folder = os.path.join("tests", intrinsic, "combo_{}".format(combination.name), "repeat_{}".format(num_repeat))
                os.makedirs(intrinsic_folder, exist_ok=True)

                with open(os.path.join(intrinsic_folder, "properties.json"), "w") as properties_file:
                    json.dump(properties, properties_file)

                with open(os.path.join(intrinsic_folder, "testbed.ll"), "w") as testbed_file:
                    testbed_file.write(testbed)
            except TypeError as e:
                print(e)

if __name__=="__main__":
    intel_vector = {}

    with open("intrinsics_all.json") as intrinsics_file:
        intrinsics = json.load(intrinsics_file)
        intel_vector = record_utils.filter_intel_vector(intrinsics)

    num_input_bytes = args.max_bits // 8

    if args.seed:
        inputs = random_bytes(num_input_bytes, args.seed)
    else:
        inputs = combine_test_input_chunks(num_input_bytes, args.test_index)

    for intrinsic in sorted(intel_vector.keys()):
        properties = intel_vector[intrinsic]
        generate_store_testbed(intrinsic=intrinsic,
                               properties=properties,
                               n_input_bits=args.max_bits,
                               inputs=inputs)
