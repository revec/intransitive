import re

def filter(pattern, records):
    return {key: value for key, value in records.items()
                       if re.match(pattern, key)}

def filter_sse2(records):
    return filter(".+sse2_", records)

def filter_avx(records):
    return filter(".+avx_", records)

def filter_avx2(records):
    return filter(".+avx2_", records)
