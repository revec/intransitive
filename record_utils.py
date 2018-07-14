import re

re_sse2 = ".+sse2_"
re_avx = ".+avx_"
re_avx2 = ".+avx2_"
#re_intel_vector = "({})|({})|({})".format(re_sse2, re_avx, re_avx2)

# TODO: incorporate avx512 - need Xeon test platform
# TODO: incorporate mmx - should update utilities.get_type for llvm_x86mmx_ty
# TODO: Add ssse3
intel_vector_sets = [
    "sse",
    "sse2",
    "sse3",
    "sse41",
    "sse42",
    "avx",
    "avx2",
    "fma",
    "avx512",
    #"3dnow",
    #"3dnowa",
    #"mmx",
]

def intrinsic_name_to_ir(name):
    # TODO: This is a hacky conversion that is specific to the
    #       format of vector intrinsics. It should ideally be
    #       extracted from TableGen.

    m = re.match(r"int_(.+)$", name)
    if m:
        name = m.group(1)

    return "llvm." + ".".join(name.split("_"))

def filter(pattern, records):
    return {key: value for key, value in records.items()
                       if re.match(pattern, key)}

def filter_intel_vector(records):
    # Build a regular expression
    regs = []
    for instr_set in intel_vector_sets:
        regs.append("(int_x86_{}_)".format(instr_set))
    re_intel_vector = "|".join(regs)

    return filter(re_intel_vector, records)

def filter_sse2(records):
    return filter(re_sse2, records)

def filter_avx(records):
    return filter(re_avx, records)

def filter_avx2(records):
    return filter(re_avx2, records)
