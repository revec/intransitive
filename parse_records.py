#!/usr/bin/env python3

import json
import re

import record_utils

#NAME_FILTER = "sse2|avx2"
TOKEN_DELIMETER_RE = r"\W+|,"

def parse_value(raw_value):
    raw_value = raw_value.strip()

    m = re.fullmatch(r'[0-9]+', raw_value)
    if m:
        # integer
        return int(raw_value)

    m = re.fullmatch(r'"(.*)"', raw_value)
    if m:
        # string
        return m.group(1)

    m = re.fullmatch(r"\[(.*)\]", raw_value)
    if m:
        # array
        value = []
        raw_value_list = m.group(1)
        for token in re.split(r",", raw_value_list):
            value.append(parse_value(token))
        return value

    return raw_value

def parse_property(line):
    """Parse a property assignment.

    Args:
        line: (str) The assignment. Example:
                    "list<LLVMType> ParamTypes = [llvm_v2f64_ty, llvm_v2f64_ty];"
    """
    line = line.rstrip(";")
    tokens = line.split(maxsplit=3)

    ty, prop, _, raw_value = tokens

    value = parse_value(raw_value)

    return (prop, value)

def parse_record(record_text):
    record_name = record_text[0].split(" ")[1]
    record_name_ir = record_utils.intrinsic_name_to_ir(record_name)

    properties = {}
    for property_line in record_text[1:-1]:
        prop, value = parse_property(property_line)
        properties[prop] = value

    properties["LLVMFunction"] = record_name_ir

    return (record_name, properties)

def parse_record_file(record_file):
    raw_records = record_file.read().split("\n")
    records = []

    i = 0
    while i < len(raw_records):
        if raw_records[i].startswith("def"):
            # Find the closing brace
            j = i
            while "}" not in raw_records[j]:
                j += 1

            # Parse a list of lines corresponding to a record
            raw_record = raw_records[i:j+1]
            record = parse_record(raw_record)
            if record:
                records.append(record)

            i = j+1
        else:
            i += 1

    return records

if __name__=="__main__":
    with open("IntrinsicRecords.td", "r") as f:
        records = parse_record_file(f)

        records = dict(records)
        json.dump(records, open("intrinsics_all.json", "w"))

        sse2 = record_utils.filter_sse2(records)
        json.dump(sse2, open("intrinsics_sse2.json", "w"))

        avx2 = record_utils.filter_avx2(records)
        json.dump(avx2, open("intrinsics_avx2.json", "w"))

        avx = record_utils.filter_avx(records)
        json.dump(avx, open("intrinsics_avx.json", "w"))

