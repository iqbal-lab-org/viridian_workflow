#!/usr/bin/env python3
import json
import sys
from collections import defaultdict
from intervaltree import Interval

import pysam
from viridian_workflow import primers


def score(matches):
    """Assign winning amplicon set id based on match stats"""

    # naive: take max of all bins
    m = 0
    winner = None
    for k, v in matches.items():
        if v >= m:
            m = v
            winner = k
    return winner


def read_interval(read):
    """determine template start and end coords for either a single read or
    paired reads
    """
    if read.is_paired:
        if not read.is_reverse:
            start = read.reference_start
            end = read.reference_start + read.template_length
            return start, end

        else:
            start = read.next_reference_start
            end = read.next_reference_start - read.template_length
            return start, end
    else:
        return read.reference_start, read.reference_end


def annotate_read(read, match):
    """Set the match details for a read"""
    raise NotImplementedError


def match_read_to_amplicons(read, amplicon_sets):
    matches = {}
    for amplicons in amplicon_sets:
        m = amplicons.match(*read_interval(read))
        if m:
            matches[amplicons.name] = m
    return matches


def match_reads(reads, amplicon_sets):
    """given a stream of reads, yield reads with a set of matched amplicons"""
    for read in reads:
        if read.is_unmapped:
            continue

        matches = match_read_to_amplicons(read, amplicon_sets)
        yield read, matches


def detect(amplicon_sets, reads):
    """Generate amplicon match stats and identify closest set of
    matching amplicons
    """

    matches = {}
    for aset in amplicon_sets:
        matches[aset.name] = 0
        # other stats for stuff like amplicon containment and
        # ambiguous match counts

    for read, amplicon_matches in match_reads(reads, amplicon_sets):
        for a in amplicon_matches:
            # unambiguous match for the read
            if len(amplicon_matches[a]) == 1:
                matches[a] += 1

    return score(matches)


def pysam_open_mode(filename):
    if filename.endswith(".sam"):
        return ""
    elif filename.endswith(".bam"):
        return "b"
    else:
        raise Exception(f"Filename {filename} does not end with .sam or .bam")


def amplicon_set_counts_to_naive_total_counts(scheme_counts):
    counts = defaultdict(int)
    for scheme_tuple, count in scheme_counts.items():
        for scheme in scheme_tuple:
            counts[scheme] += count
    return counts


def gather_stats_from_bam(infile, bam_out, amplicon_sets):
    open_mode_in = "r" + pysam_open_mode(infile)
    aln_file_in = pysam.AlignmentFile(infile, open_mode_in)
    if bam_out is not None:
        open_mode_out = "w" + pysam_open_mode(bam_out)
        aln_file_out = pysam.AlignmentFile(bam_out, open_mode_out, template=aln_file_in)

    stats = {
        "unpaired_reads": 0,
        "reads1": 0,
        "reads2": 0,
        "total_reads": 0,
        "mapped": 0,
        "match_any_amplicon": 0,
        "read_lengths": defaultdict(int),
        "amplicon_scheme_set_matches": defaultdict(int),
    }
    infile_is_paired = None
    current_read_tag = None

    for read in aln_file_in:
        if read.is_secondary or read.is_supplementary:
            continue

        if infile_is_paired is None:
            infile_is_paired = read.is_paired
        elif read.is_paired != infile_is_paired:
            raise Exception("Reads must be all paired or all unpaired")

        stats["total_reads"] += 1
        stats["read_lengths"][read.query_length] += 1
        if not read.is_unmapped:
            stats["mapped"] += 1

        if read.is_paired:
            if read.is_read1:
                if current_read_tag is not None:
                    raise Exception(
                        "Paired reads not in expected order. Cannot continue"
                    )
                stats["reads1"] += 1
                amplicon_matches = match_read_to_amplicons(read, amplicon_sets)
                # FIXME
                current_read_tag = "TODO"
                # annotate_read(read, current_read_tag, ...)
            else:
                if current_read_tag is None:
                    raise Exception(
                        "Paired reads not in expected order. Cannot continue"
                    )
                stats["reads2"] += 1
                # FIXME
                # annotate_read(read, current_read_tag, ...)
                current_read_tag = None
                amplicon_matches = None
        else:
            stats["unpaired_reads"] += 1
            amplicon_matches = match_read_to_amplicons(read, amplicon_sets)
            # FIXME
            # annotate_read(...)

        if amplicon_matches is not None and len(amplicon_matches) > 0:
            stats["match_any_amplicon"] += 1
            key = tuple(sorted(list(amplicon_matches.keys())))
            stats["amplicon_scheme_set_matches"][key] += 1

        if bam_out is not None:
            aln_file_out.write(read)

    aln_file_in.close()
    if bam_out is not None:
        aln_file_out.close()

    stats["amplicon_scheme_simple_counts"] = amplicon_set_counts_to_naive_total_counts(
        stats["amplicon_scheme_set_matches"]
    )
    stats["chosen_amplicon_scheme"] = score(stats["amplicon_scheme_simple_counts"])
    return stats
