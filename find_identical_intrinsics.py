#!/usr/bin/env python3

import argparse
from collections import defaultdict, namedtuple
import itertools
import json
import os
import re

from utilities import Combination

parser = argparse.ArgumentParser(description="Find identical intrinsics")
parser.add_argument("--log", type=str, nargs="+",
                    help="Log from generate_tests.py to process to find candidates")
parser.add_argument("--output-folder", type=str, required=True,
                    help="Folder in which to log equivalences")
args = parser.parse_args()

Configuration = namedtuple("Configuration", ["id", "combination", "repeat"])

def find_common_outputs(log_file):
    test_outputs = []
    testbed_path = None

    output_to_intrinsics = defaultdict(list)

    for line in log_file:
        m = re.match("TEST START (.+/testbed)", line)
        if m:
            testbed_path = m.group(1)
        elif re.match("TEST STOP", line):
            # TODO: Add other possible byte shuffles
            output = "".join(test_outputs)
            test_outputs.clear()

            output_to_intrinsics[output].append(testbed_path)
        else:
            test_outputs.append(line.strip())

    return output_to_intrinsics


def refine_equivalences(equivalences, candidate_equivalences):
    """For each instruction/configuration, intersect its set of equivalences with a candidate set.

    Args:
        equivalences: dict (str -> set). Maps configuration name to a set of names that
                      are currently thought to be equivalent.
        candidate_equivalences: list of sets. Proposed equivalence sets.
    """
    for candidate_set in candidate_equivalences:
        for instruction in list(candidate_set):
            if instruction in equivalences:
                # Refine equivalence set
                equivalences[instruction].intersection_update(candidate_set)
            else:
                # First time we've seen this - set the equiv set
                equivalences[instruction] = set(candidate_set)


def recommend_conversions(equivalence_lists):
    pairs = []

    for equivs in equivalence_lists:
        configurations = set()

        # Parse intrinsic configuration name
        for config_str in equivs:
            _, intrin_id, combination, repeat, __ = config_str.split("/")

            _, __, combination = combination.partition("_")
            combination = Combination[combination]

            repeat = int(repeat.partition("_")[2])

            configuration = Configuration(id=intrin_id,
                                          combination=combination,
                                          repeat=repeat)
            configurations.add(configuration)

        # Filter out unnecessary pairs
        deduplicated = set()
        for config in configurations:
            if config.combination == Combination.CONSECUTIVE:
                alt_config = Configuration(id=config.id,
                                           combination=Combination.INTERLEAVED,
                                           repeat=config.repeat)
            elif config.combination == Combination.INTERLEAVED:
                alt_config = Configuration(id=config.id,
                                           combination=Combination.CONSECUTIVE,
                                           repeat=config.repeat)

            if alt_config in configurations:
                config = Configuration(id=config.id,
                                       combination=Combination.ANY,
                                       repeat=config.repeat)

            deduplicated.add(config)

        if (len(deduplicated) > 6):
            print(len(deduplicated), deduplicated)

        if (len(deduplicated) > 1):
            combinations = itertools.combinations(deduplicated, 2)
            pairs.extend(combinations)

    for pair in pairs:
        m = re.match("int_x86_(sse|sse2|avx|avx2)_(u?)comi", pair[0].id)
        if m:
            if m.group(2) == "u" and re.match("int_x86_{}_comi".format(m.group(1)), pair[1].id):
                continue
            elif m.group(2) == "" and re.match("int_x86_{}_ucomi".format(m.group(1)), pair[1].id):
                continue

        yield pair


def serialize_conversions(conversions, fp):
    conversions_serializable = []

    for conversion in conversions:
        conversion_dicts = []
        for config in conversion:
            config_dict = dict(config._asdict())
            config_dict["combination"] = config_dict["combination"].name
            conversion_dicts.append(config_dict)
        conversions_serializable.append(conversion_dicts)

    json.dump(conversions_serializable, fp)

if __name__=="__main__":
    # Generate equality candidates from input test log files

    equivalences = {}

    # Build & refine equivalence set by candidates from test logs
    for log_path in args.log:
        with open(log_path, "r") as log_file:
            common_outputs = find_common_outputs(log_file)
            total = sum(map(len, equivalences.values()))
            print(log_path, total)
            refine_equivalences(equivalences, common_outputs.values())

    equivalences_dedup = set()
    for equiv_set in equivalences.values():
        equiv_set = frozenset(equiv_set)
        equivalences_dedup.add(equiv_set)

    # Write equivalences to a JSON file
    equivalence_lists = []
    missed_list = []
    for equiv_set in equivalences_dedup:
        if len(equiv_set) > 1:
            equiv_list = list(equiv_set)
            equiv_list.sort()
            equivalence_lists.append(equiv_list)
        else:
            missed_list.extend(list(equiv_set))
    missed_list.sort()

    json.dump(equivalence_lists,
              open(os.path.join(args.output_folder, "test_equivalences.json"), "w"))

    json.dump(missed_list,
              open(os.path.join(args.output_folder, "test_missed.json"), "w"))

    conversions = recommend_conversions(equivalence_lists)
    with open(os.path.join(args.output_folder, "test_conversions.json"), "w") as conversions_f:
        serialize_conversions(conversions, conversions_f)

