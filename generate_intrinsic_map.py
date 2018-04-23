#!/usr/bin/env python3

import argparse
import datetime
import json

parser = argparse.ArgumentParser(description="Generate header file containing intrinsic conversions")
parser.add_argument("--input", type=str, required=False, default="logs/test_conversions.json",
                    help="Path to conversions JSON file")
parser.add_argument("--output", type=str, required=False, default="gen/intrinsicWideningMap.h",
                    help="Path to which to output header file")
args = parser.parse_args()


def make_map_source(conversions):
    date = datetime.date.today().strftime("%B %d, %Y")
    source = """// Generated {}

// A map encoding lane-widening intrinsic conversions
static DenseMap<unsigned, std::pair<unsigned, int>> intrinsicWideningMap;

static void initializeIntrinsicWideningMap() {{
""".format(date)

    # Sort key assignment for aesthetics
    conversions.sort(key=lambda conversion: conversion[0]["id"])

    for conversion in conversions:
        base = conversion[0]
        target = conversion[1]

        # Remove int_ prefix from IDs
        base_key = base["id"].partition("int_")[2]
        target_key = target["id"].partition("int_")[2]

        # NOTE: The basic map encoding only specifies k-to-1 conversions
        assert(target["repeat"] == 1)
        assert(base_key != target_key)

        source += "  intrinsicMap[Intrinsic::{}] = std::make_pair<unsigned, int>(Intrinsic::{}, {});\n".format(base_key, target_key, base["repeat"])

    source += "}\n"

    return source


if __name__=="__main__":
    conversions = []

    with open(args.input, "r") as input_f:
        conversions = json.load(input_f)

    header_source = make_map_source(conversions)

    with open(args.output, "w") as output_f:
        output_f.write(header_source)

    print(header_source)

