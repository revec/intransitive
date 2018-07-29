#!/usr/bin/env python3

import argparse
from collections import defaultdict
import coloredlogs
import datetime
import json
import logging

from jinja2 import Template

coloredlogs.install()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def make_map_source(conversions):
    # date = datetime.date.today().strftime("%B %d, %Y")

    with open("templates/IntrinsicConversion.h.tmpl", "r") as template_f:
        template = Template(template_f.read())
    
    output_conversions = format_conversions_all(conversions)
    source = template.render(lane_widening_conversions=output_conversions)
    return source

def format_conversions_all(conversions):
    # Load a list of intrinsic IDs that appear to be removed
    # from the llvm::Intrinsic namespace
    removed_intrinsics = set()
    with open("templates/removed_intrinsics.txt", "r") as id_f:
        for IID in id_f:
            removed_intrinsics.add(IID.strip())

    # Collect targets for each source configuration
    collected = defaultdict(set)
    for base, target in conversions:
        if ((base["combination"] not in ("VERTICAL", "ANY") or target["combination"] not in ("VERTICAL", "ANY"))
                and base["repeat"] != 1 and target["repeat"] != 1):
            logger.warn(
                "Only lane-widening (vertical) combinations are supported by the Revectorizer, skipping pair:")
            logger.warn("    Base: %s", base)
            logger.warn("  Target: %s", target)
            continue

        if target["repeat"] != 1:
            logger.warn(
                "Revectorizer only can perform k-to-1 intrinsic call conversions, but target %s has higher repeat", target)
            continue
        
        # Remove int_ prefix from IDs
        base_key = base["id"].partition("int_")[2]
        target_key = target["id"].partition("int_")[2]
        assert base_key != target_key

        if base_key in removed_intrinsics or target_key in removed_intrinsics:
            logger.warn("Skipping conversion with removed intrinsic(s):")
            logger.warn("    Base: %s", base)
            logger.warn("  Target: %s", target)
            continue

        VF = base["repeat"]
        collected[base_key].add((VF, target_key))
    
    return collected.items()

    #for conversion in conversions:
    #    base = conversion[0]
    #    target = conversion[1]

    #    # Remove int_ prefix from IDs
    #    base_key = "Intrinsic::" + base["id"].partition("int_")[2]
    #    target_key = "Intrinsic::" + target["id"].partition("int_")[2]

    #    # NOTE: The basic map encoding only specifies k-to-1 conversions
    #    assert(target["repeat"] == 1)
    #    assert(base_key != target_key)

    #    yield (base_key, target_key, base["repeat"])


if __name__=="__main__":
    parser = argparse.ArgumentParser(description="Generate header file containing intrinsic conversions")
    parser.add_argument("--input", type=str, required=False, default="logs/test_conversions.json",
                        help="Path to conversions JSON file")
    parser.add_argument("--output", type=str, required=False, default="gen/IntrinsicConversion.h",
                        help="Path to which to output header file")
    args = parser.parse_args()

    conversions = []

    with open(args.input, "r") as input_f:
        conversions = json.load(input_f)

    header_source = make_map_source(conversions)

    with open(args.output, "w") as output_f:
        output_f.write(header_source)

    print(header_source)

