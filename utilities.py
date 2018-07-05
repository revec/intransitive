#!/usr/bin/env python3

import enum
import re

from colorama import Fore, Style

type_to_format = {
    "i8": "b", # signed char
    "i16": "h",
    "i32": "i",
    "i64": "q",
}

class Combination(enum.Enum):
    CONSECUTIVE = 1
    INTERLEAVED = 2
    ANY = 3

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

    # TODO: Possibly remove support for MMX
    #if identifier == "llvm_x86mmx_ty":
    #    return "<1 x i64>", 1, "i64", 64

    raise TypeError(Fore.RED + "Bad type: {}".format(identifier) + Style.RESET_ALL)


