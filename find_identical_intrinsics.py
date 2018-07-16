#!/usr/bin/env python3

import argparse
from collections import defaultdict, namedtuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import difflib
import itertools
import json
import logging
import math
import os
from pprint import pprint
import re

import coloredlogs
from colorama import Fore, Style
import Levenshtein

from IPython import embed
import pdb

from utilities import Combination, get_type, tqdm_parallel_map

coloredlogs.install()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

parser = argparse.ArgumentParser(description="Find identical intrinsics")
parser.add_argument("--log", type=str, nargs="+",
                    help="Log from generate_tests.py to process to find candidates")
parser.add_argument("--output-folder", type=str, required=True,
                    help="Folder in which to log equivalences")
args = parser.parse_args()


class Configuration(object):
    def __init__(self, id, combination, repeat):
        self.id = id
        self.combination = combination
        self.repeat = repeat

        parts = self.id.split("_")
        self.architecture = parts[1]
        self.instruction_set = parts[2]
        self.operation = "_".join(parts[3:])

    def to_dict(self):
        return {
            "id": self.id,
            "combination": self.combination.name,
            "repeat": self.repeat,
        }

    def __repr__(self):
        return "Configuration({id}, {combination}, {repeat})".format(
                id=self.id,
                combination=self.combination.name,
                repeat=self.repeat)

    def __hash__(self):
        # This is a terrible hash, but solves a non-determinacy bug in which
        # filter_high_repetitions produces variable length outputs
        return 0
        #return hash((self.id, self.combination.name, self.repeat))

    def __eq__(self, other):
        return (self.id == other.id and
                self.combination.name == other.combination.name and
                self.repeat == other.repeat)


def find_common_outputs(log_path):
    """Create a map from test output to a list of intrinsics that produced that output"""
    test_outputs = []
    testbed_path = None

    output_to_intrinsics = defaultdict(list)

    with open(log_path, "r") as log_file:
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

    return list(output_to_intrinsics.values())


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


def filter_ucomi(conversions):
    """Filter out false equivalences between sse2.comi... and sse2.ucomi...

    The intrinsics sse2.comi<lt/le/gt/ge> and see2.ucomi<lt/le/gt/ge> have different exception handing behavior.
    """
    for pair in conversions:
        m = re.match("int_x86_([a-z0-9]+)_(u?)comi", pair[0].id)
        if m:
            if m.group(2) == "u" and re.match("int_x86_([a-z0-9]+)_comi", pair[1].id):
                continue
            elif m.group(2) == "" and re.match("int_x86_([a-z0-9]+)_ucomi", pair[1].id):
                continue

        yield pair


def filter_high_repetitions(conversions):
    """Simplify conversions

    Example: don't convert 4x sse2 into 2x avx2, if a 2x sse2 to 1x avx2 conversion is available.
    """
    simple_conversions = set()
    for conversion in conversions:
        repeat_0 = conversion[0].repeat
        repeat_1 = conversion[1].repeat
        gcd = math.gcd(repeat_0, repeat_1)

        if gcd > 1:
            simple_conversion = (
                Configuration(id=conversion[0].id,
                              combination=conversion[0].combination,
                              repeat=(repeat_0 // gcd)),
                Configuration(id=conversion[1].id,
                              combination=conversion[1].combination,
                              repeat=(repeat_1 // gcd))
            )

            # Add the reduced conversion, if it doesn't exist
            simple_conversions.add(simple_conversion)
        else:
            # Simplest conversion available
            simple_conversions.add(conversion)

    return list(simple_conversions)


def order_pairs(conversions):
    """Order conversion tuples: (source_config, target_config)"""
    ordered_instruction_sets = ["sse", "sse2", "sse3", "sse41", "avx", "avx2", "fma", "avx512"]

    for conversion in conversions:
        a, b = conversion

        VF = a.repeat / b.repeat
        power = ordered_instruction_sets.index(b.instruction_set) - ordered_instruction_sets.index(a.instruction_set)

        # Heuristic: Consolidate repeated intrinsics
        if VF > 1:
            yield conversion
        elif VF < 1:
            yield (b, a)
        elif a.id != b.id:
            if power > 0:
                yield conversion
            elif power < 0:
                yield conversion
            else:
                logger.warn("Unclear conversion direction for intrinsics:\n  base:   {}\n  target: {}".format(a, b))


def filter_differing_arguments(conversions):
    with open("intrinsics_all.json", "r") as intrinsics_f:
        intrinsics = json.load(intrinsics_f)

    for conversion in conversions:
        params0 = intrinsics[conversion[0].id]["ParamTypes"]
        params1 = intrinsics[conversion[1].id]["ParamTypes"]

        if len(params0) == len(params1):
            element_types0 = tuple(map(lambda ty: get_type(ty)[2], params0))
            element_types1 = tuple(map(lambda ty: get_type(ty)[2], params1))

            if element_types0 == element_types1:
                yield conversion


def pick_target(base_configuration, targets):
    """Given one or more target conversion candidates of the same instruction set, pick one"""
    assert len(targets)

    # Maximize the vectorization factor
    min_repeat = min(map(lambda conf: conf.repeat, targets))
    targets = filter(lambda conf: conf.repeat == min_repeat, targets)

    # Select targets with the most similar operation names
    distances = {conf: Levenshtein.distance(base_configuration.operation, conf.operation) for conf in targets}
    min_distance = min(distances.values())
    targets = [conf for conf, distance in distances.items() if distance == min_distance]

    # Remove an unnecessary VERTICAL configuration if the ANY configuration is present
    # FIXME: recommend_conversions should make this unnecessary
    filtered = []
    for target in targets:
        if (target.combination == Combination.ANY or
            Configuration(id=target.id, combination=Combination.ANY, repeat=target.repeat) not in targets):
            filtered.append(target)
    targets = filtered

    if len(targets) > 1:
        logger.error("Even after filtering, multiple conversion candidates for {}. Picking first.".format(base_configuration))
        for target in targets:
            logger.error("    target: {}".format(target))

    assert len(targets)
    return targets[0]


def remove_duplicate_targets(conversions):
    """If multiple conversions are possible for an intrinsic configuration, choose one per target instruction set, or skip"""
    # Build two level map: base configuration => target instruction_set => list of targets
    conversion_map = defaultdict(lambda: defaultdict(list))
    for conversion in conversions:
        base, target = conversion
        conversion_map[base][target.instruction_set].append(target)

    for base, targets_by_instruction_set in conversion_map.items():
        for targets in targets_by_instruction_set.values():
            # Choose one target out of candidates in the same instruction set
            target = pick_target(base, targets)
            yield (base, target)


def recommend_conversions(equivalence_lists):
    """Given lists of equivalent testbeds, generate conversion pairs."""
    pairs = []

    for equivalence_list in equivalence_lists:
        equivalent_configurations = set()

        for config_str in equivalence_list:
            # Parse intrinsic configuration name
            _, intrin_id, combination, repeat, __ = config_str.split("/")

            _, __, combination = combination.partition("_")
            combination = Combination[combination]

            repeat = int(repeat.partition("_")[2])

            configuration = Configuration(id=intrin_id,
                                          combination=combination,
                                          repeat=repeat)
            equivalent_configurations.add(configuration)

        # If both vertical and horizontal combinations are possible, specify only an ANY combination
        deduplicated = set()
        for config in equivalent_configurations:
            alt_config = Configuration(id=config.id,
                                       combination=Combination.VERTICAL if config.combination == Combination.HORIZONTAL else Combination.HORIZONTAL,
                                       repeat=config.repeat)

            if alt_config in equivalent_configurations:
                deduplicated.add(Configuration(config.id, Combination.ANY, config.repeat))
            else:
                deduplicated.add(config)

        if len(deduplicated) > 1:
            combinations = itertools.combinations(deduplicated, 2)
            pairs.extend(combinations)

    # Filter out semantically different instructions with rules
    filter_steps = [
        "filter_ucomi",
        "filter_high_repetitions",
        "filter_differing_arguments",
        "order_pairs",
        "remove_duplicate_targets",
    ]

    for filter_fn_name in filter_steps:
        num_pairs = len(pairs)
        filter_fn = eval(filter_fn_name)
        pairs = list(filter_fn(pairs))
        logger.info("FILTER ({}): {} => {} conversion pairs".format(filter_fn_name, num_pairs, len(pairs)))

    return pairs


def serialize_conversions(conversions, fp):
    conversions_serializable = []

    for conversion in conversions:
        conversion_dicts = []
        for config in conversion:
            config_dict = config.to_dict()
            conversion_dicts.append(config_dict)
        conversions_serializable.append(conversion_dicts)

    json.dump(conversions_serializable, fp)

if __name__=="__main__":
    # Build & refine equivalence set by candidates from test logs
    logger.info("Parsing test log files to extract equivalence lists")
    executor = ProcessPoolExecutor()
    all_log_equivalences = tqdm_parallel_map(executor, find_common_outputs, args.log)

    # Given these equivalence lists, build and refine equivalence sets
    equivalences = {}
    for log_equivalences in all_log_equivalences:
        refine_equivalences(equivalences, log_equivalences)

    final_count = sum(map(len, equivalences.values()))
    logger.info("REFINED equivalences {:6}".format(final_count))

    # Remove duplicate equivalence sets
    equivalences_dedup = set()
    for equiv_set in equivalences.values():
        equiv_set = frozenset(equiv_set)
        equivalences_dedup.add(equiv_set)

    # Convert sets into lists, find missed instructions
    equivalence_lists = []  # Elements are lists of equivalent testbeds
    missed_list = []
    for equiv_set in equivalences_dedup:
        if len(equiv_set) > 1:
            equiv_list = list(equiv_set)
            equiv_list.sort()
            equivalence_lists.append(equiv_list)
        else:
            missed_list.extend(list(equiv_set))
    missed_list.sort()

    # Write equivalences to a JSON file
    with open(os.path.join(args.output_folder, "test_equivalences.json"), "w") as equiv_f:
        json.dump(equivalence_lists, equiv_f)

    with open(os.path.join(args.output_folder, "test_missed.json"), "w") as missed_f:
        json.dump(missed_list, missed_f)

    # Find pairs of conversions from lists of equivalent intrinsics
    conversions = recommend_conversions(equivalence_lists)

    logger.info("Found {} conversions".format(len(conversions)))
    for conversion in conversions:
        VF = conversion[0].repeat / conversion[1].repeat
        if "psrl_q" in conversion[0].id:
            logger.info("  VF: {}, {} => {}".format(VF, *conversion))

    with open(os.path.join(args.output_folder, "test_conversions.json"), "w") as conversions_f:
        serialize_conversions(conversions, conversions_f)

