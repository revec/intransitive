import re

re_sse2 = ".+sse2_"
re_avx = ".+avx_"
re_avx2 = ".+avx2_"
re_intel_vector = "({})|({})|({})".format(re_sse2, re_avx, re_avx2)

def filter(pattern, records):
    return {key: value for key, value in records.items()
                       if re.match(pattern, key)}

def filter_intel_vector(records):
    return filter(re_intel_vector, records)

def filter_sse2(records):
    return filter(re_sse2, records)

def filter_avx(records):
    return filter(re_avx, records)

def filter_avx2(records):
    return filter(re_avx2, records)
