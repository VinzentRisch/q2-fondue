# ----------------------------------------------------------------------------
# Copyright (c) 2021, QIIME 2 development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------

import os
import re
import gzip
import itertools
import tempfile
from subprocess import run
from q2_types.per_sample_sequences import \
    (CasavaOneEightSingleLanePerSampleDirFmt)


def _run_cmd_fasterq(acc: str, output_dir: str, threads: int,
                     retries: int):
    """
    Helper function running fasterq-dump `general_retries` times
    """

    print("Downloading sequences of sample: {}...".format(acc))

    acc_fastq_single = os.path.join(output_dir,
                                    acc + '.fastq')
    acc_fastq_paired = os.path.join(output_dir,
                                    acc + '_1.fastq')

    cmd_fasterq = ["fasterq-dump",
                   "-O", output_dir,
                   "-t", output_dir,
                   "-e", str(threads),
                   acc]

    # try "retries" times to get sequence data
    while retries >= 0:
        result = run(cmd_fasterq, text=True, capture_output=True)

        if not (os.path.isfile(acc_fastq_single) |
                os.path.isfile(acc_fastq_paired)):
            retries -= 1
            print('retrying {} times'.format(retries+1))
        else:
            retries = -1

    return result


def _run_fasterq_dump_for_all(sample_ids, tmpdirname, threads,
                              general_retries):
    """
    Helper function that runs fasterq-dump for all ids in study-ids
    """
    for acc in sample_ids:
        result = _run_cmd_fasterq(acc, tmpdirname, threads,
                                  general_retries)

        if len(os.listdir(tmpdirname)) == 0:
            # raise error if all general_retries attempts failed
            raise ValueError('{} could not be downloaded with the '
                             'following fasterq-dump error '
                             'returned: {}'
                             .format(acc, result.stderr))
        else:
            continue


def _process_downloaded_sequences(output_dir):
    """
    Helper function that renames single-read and
    paired-end sequences according to casava file format
    and outputs list of single-read and paired-end sequence
    filenames.
    """

    # gzip all remaining files in folder
    # todo: verify if gzip can be left out
    cmd_gzip = ["gzip",
                "-r", output_dir]
    # todo: try, except
    run(cmd_gzip, text=True, capture_output=True)

    # rename all files to casava format & save single and paired
    # file names to list
    ls_single, ls_paired = [], []

    for filename in os.listdir(output_dir):
        if filename.endswith('_1.fastq.gz'):
            # double read _1
            acc = re.search(r'(.*)_1\.fastq\.gz$', filename).group(1)
            new_name = '%s_00_L001_R1_001.fastq.gz' % (acc)
            ls_paired.append(new_name)
        elif filename.endswith('_2.fastq.gz'):
            # double read _2
            acc = re.search(r'(.*)_2\.fastq\.gz$', filename).group(1)
            new_name = '%s_00_L001_R2_001.fastq.gz' % (acc)
            ls_paired.append(new_name)
        else:
            # single reads
            acc = re.search(r'(.*)\.fastq\.gz$', filename).group(1)
            new_name = '%s_00_L001_R1_001.fastq.gz' % (acc)
            ls_single.append(new_name)

        os.rename(os.path.join(output_dir, filename),
                  os.path.join(output_dir, new_name))

    return ls_single, ls_paired


def _read_fastq_seqs(filepath):
    # function copied from q2_demux._demux import _read_fastq_seqs

    # Originally func is adapted from @jairideout's SO post:
    # http://stackoverflow.com/a/39302117/3424666
    fh = gzip.open(filepath, 'rt')
    for seq_header, seq, qual_header, qual in itertools.zip_longest(*[fh] * 4):
        yield (seq_header.strip(), seq.strip(), qual_header.strip(),
               qual.strip())


def _write2casava_dir_single(tmpdirname, casava_result_path,
                             ls_files_2_consider):
    """
    Helper function that writes downloaded sequence files
    from tmpdirname to casava_result_path following single
    read sequence rules
    """
    # Edited from original in: q2_demux._subsample.subsample_single
    for filename in os.listdir(tmpdirname):
        if filename in ls_files_2_consider:
            fwd_path_in = os.path.join(tmpdirname, filename)
            fwd_path_out = str(casava_result_path.path / filename)

            with gzip.open(str(fwd_path_out), mode='w') as fwd:
                for fwd_rec in _read_fastq_seqs(fwd_path_in):
                    fwd.write(('\n'.join(fwd_rec) + '\n').encode('utf-8'))


def _write2casava_dir_double(tmpdirname, casava_result_path,
                             ls_files_2_consider):
    """
    Helper function that writes downloaded sequence files
    from tmpdirname to casava_result_path following double
    read sequence rules
    """
    # Edited from original in: q2_demux._subsample.subsample_paired
    # ensure correct order of file names:
    ls_files_sorted = sorted(ls_files_2_consider)

    # iterate and save
    for i in range(0, len(ls_files_sorted), 2):
        filename_1 = ls_files_sorted[i]
        filename_2 = ls_files_sorted[i+1]

        fwd_path_in = os.path.join(tmpdirname, filename_1)
        fwd_path_out = str(casava_result_path.path / filename_1)
        rev_path_in = os.path.join(tmpdirname, filename_2)
        rev_path_out = str(casava_result_path.path / filename_2)

        with gzip.open(str(fwd_path_out), mode='w') as fwd:
            with gzip.open(str(rev_path_out), mode='w') as rev:
                file_pair = zip(_read_fastq_seqs(fwd_path_in),
                                _read_fastq_seqs(rev_path_in))
                for fwd_rec, rev_rec in file_pair:
                    fwd.write(('\n'.join(fwd_rec) + '\n').encode('utf-8'))
                    rev.write(('\n'.join(rev_rec) + '\n').encode('utf-8'))


def get_sequences(
        sample_ids: list,
        general_retries: int = 2,
        threads:
        int = 6) -> (CasavaOneEightSingleLanePerSampleDirFmt,
                     CasavaOneEightSingleLanePerSampleDirFmt):
    """
    Fetches single-read and paired-end sequences based on provided
    accession IDs.

    Function uses SRA-toolkit fasterq-dump to get single-read and paired-end
    sequences of accession IDs. It supports multiple tries (`general_retries`)
    and can use multiple `threads`.

    Args:
        sample_ids (List[str]): List of all sample IDs to be fetched.
        general_retries (int, default=2): Number of retries to fetch sequences.
        threads (int, default=6): Number of threads to be used in parallel.

    Returns:
        Two directories with fetched single-read and paired-end sequences
        respectively for provided accession IDs. If the provided accession IDs
        only contain one type of sequences (single-read or paired-end) the
        other directory is empty (with artificial ID starting with xxx_)
    """
    casava_out_single = CasavaOneEightSingleLanePerSampleDirFmt()
    casava_out_double = CasavaOneEightSingleLanePerSampleDirFmt()

    with tempfile.TemporaryDirectory() as tmpdirname:
        # run fasterq-dump for all accessions
        _run_fasterq_dump_for_all(sample_ids, tmpdirname, threads,
                                  general_retries)

        # processing downloaded files
        ls_single_files, ls_paired_files = _process_downloaded_sequences(
            tmpdirname)

        # write downloaded single-read seqs from tmp to casava dir
        if len(ls_single_files) == 0:
            print('No single-read sequences available for these StudyIDs')
            # create empty CasavaDirFmt due to Q2 not supporting optional
            # output types
            new_empty_name = 'xxx_00_L001_R1_001.fastq.gz'
            path_out = str(casava_out_single.path / new_empty_name)
            with gzip.open(str(path_out), mode='w'):
                pass
        else:
            _write2casava_dir_single(tmpdirname, casava_out_single,
                                     ls_single_files)

        # write downloaded paired-end seqs from tmp to casava dir
        if len(ls_paired_files) == 0:
            print('No paired-end sequences available for these StudyIDs')
            # create empty CasavaDirFmt due to Q2 not supporting optional
            # output types
            fwd_empty_name = 'xxx_00_L001_R1_001.fastq.gz'
            rev_empty_name = 'xxx_00_L001_R2_001.fastq.gz'

            fwd_path_out = str(casava_out_double.path / fwd_empty_name)
            rev_path_out = str(casava_out_double.path / rev_empty_name)
            with gzip.open(str(fwd_path_out), mode='w'):
                pass
            with gzip.open(str(rev_path_out), mode='w'):
                pass
        else:
            _write2casava_dir_double(tmpdirname, casava_out_double,
                                     ls_paired_files)

    return casava_out_single, casava_out_double