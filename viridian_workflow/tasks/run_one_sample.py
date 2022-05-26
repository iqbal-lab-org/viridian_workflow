import logging
import subprocess
from viridian_workflow import run, utils


def load_amplicon_index(index_tsv, subset=None):
    index = {}
    for name, tsv in open(index_tsv):
        if name == "Name" and tsv == "File":
            continue
        index[name] = tsv

    if subset:
        for key in subset:
            if key not in index:
                raise Exception(
                    f"Selected subset of amplicon schemes ({','.join(subset)}) are not in the builtin set: {','.join(index.keys())}"
                )
            else:
                del index[key]
    return index


def run(options):
    fq1, fq2 = utils.check_tech_and_reads_opts_and_get_reads(options)

    if options.force:
        logging.info(f"--force option used, so deleting {options.outdir} if it exists")
        subprocess.check_output(f"rm -rf {options.outdir}", shell=True)

    # New function run.run_pipeline wants a list of fastq files
    fqs = [fq1]
    if fq2 is None:
        fqs = [fq1, fq2]

    # Build the index of built-in schemes, possibly subsetted
    amplicon_index = load_amplicon_index("", subset=options.built_in_amp_schemes)

    # If a set is forced, select it from the possibly subsetted built-ins
    chosen_amplicon_set = None
    if options.force_amp_scheme:
        # If they're forcing an amplicon scheme but have disabled all built-ins
        # this is an error. We may want to allow this to enable them to force
        # a custom scheme
        if options.amp_schemes_tsv and not options.built_in_schemes:
            raise Exception("Can only force amplicon scheme from built-in options")

        if options.force_amp_scheme in amplicon_index:
            chosen_amplicon_set = amplicon_index[options.force_amp_scheme]
        else:
            raise Exception(
                f"Chose to force amplicons scheme to be {options.force_amp_scheme}, but scheme not found. Found these: {','.join(amplicon_index.keys())}"
            )

    if options.amp_schemes_tsv:
        # if the user brings their own tsv index, ignore the built in set,
        # unless they also specified a subset from the built in set
        if options.built_in_amp_schemes:
            for name, scheme in load_amplicon_index(options.amp_schemes_tsv).items():
                amplicon_index[name] = scheme
        else:
            amplicon_index = load_amplicon_index(options.amp_schemes_tsv)

    # TODO: this needs to run and handle the keyword args
    run.run_pipeline(
        options.oudir,
        options.tech,
        fqs,
        amplicon_sets,
        ref=options.ref_fasta,
        force_amp_scheme=chosen_amplicon_set,
        keep_intermediate=options.debug,
        keep_bam=options.keep_bam,
        sample_name=options.sample_name,
        frs_threshold=options.frs_threshold,
        self_qc_depth=options.self_qc_depth,
        consensus_max_n_percent=options.max_cons_n_percent,
        max_percent_amps_fail=options.max_percent_amps_fail,
        command_line_args=options,
    )
