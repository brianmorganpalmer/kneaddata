'''
generate_db.py
Author: Andy Shi

Helper script to generate databases for the knead_data.py pipeline
Requires the BMTagger suite and NCBI BLAST.
'''

import argparse
import subprocess
import shlex
import os
import sys

def main():
    # parse command line arguments
    # note: argparse converts dashes '-' in argument prefixes to underscores '_'
    parser = argparse.ArgumentParser()
    parser.add_argument("fasta", help="input FASTA file")
    parser.add_argument("-o", "--output-prefix", 
        help="prefix for all output files")

    # assumes that bmtool, srprism, and makeblastdb are all in the user's $PATH.
    # Otherwise you can specify their locations.
    parser.add_argument("-b", "--bmtool-path", default="bmtool",
            help="path to bmtool executable")
    parser.add_argument("-s", "--srprism-path", default="srprism",
        help="path to srprism executable")
    parser.add_argument("-m", "--makeblastdb-path", default="makeblastdb",
        help="path to makeblastdb executable")

    args = parser.parse_args()

    # Take care of missing prefix
    if not args.output_prefix:
        args.output_prefix = args.fasta

    # check if input files exist
    inputs = [args.fasta, args.bmtool_path, args.srprism_path,
            args.makeblastdb_path]
    for inp in inputs:
        if not os.path.exists(inp):
            print("Could not find file " + inp)
            print("Aborting... ")
            sys.exit(1)


    # before running each command, check that output files don't already exist.
    
    # Can parallelize the below

    # bmtool
    if not os.path.exists(args.output_prefix + ".bitmask"):
        print("Running bmtool!")
        cmd = str(args.bmtool_path + " -d " + args.fasta + " -o " +
            args.output_prefix + ".bitmask -A 0 -z -w 18")
        print("The following bmtool command will be run:")
        print(cmd)
        ret = subprocess.call(shlex.split(cmd))
        if ret != 0:
            print("Something seems to have gone wrong with bmtool!")
    else:
        print("The output files for bmtool already exist! Moving on...")



    # srprism 
    srprism_ext = [".amp", ".idx", ".imp", ".map", ".pmp", ".rmp", ".ss",
            ".ssa", ".ssd"]
    srprism_files = map(lambda x: str(args.output_prefix + ".srprism" + x),
            srprism_ext)
    print("Checking for the following files:")
    print(srprism_files)

    # run if >= 1 srprism output file does not exist
    b_srprism_run = False

    for f in srprism_files:
        if not os.path.exists(f):
            b_srprism_run = True
            break

    if b_srprism_run:
        print("Running srprism!")
        cmd = str(args.srprism_path + " mkindex -i " + args.fasta + " -o " +
            args.output_prefix + " -M 7168")
        print("The following srprism command will be run:")
        print(cmd)
        ret = subprocess.call(shlex.split(cmd))
        if ret != 0:
            print("Something seems to have gone wrong with srprism!")
    else:
        print("The output files for srprism already exist! Moving on...")


    # makeblastdb
    blastdb_ext = ["nhr", "nin", "nsq"]

    blastdb_files = map(lambda x: str(args.output_prefix + x), srprism_ext)
    print("Checking for the following files:")
    print(blastdb_files)

    # run if >= 1 makeblastdb output file does not exist
    b_blastdb_run = False

    for f in blastdb_files:
        if not os.path.exists(f):
            b_blastdb_run = True
            break

    if b_blastdb_run:
        print("Running makeblastdb!")
        cmd = str(args.makeblastdb_path + " -in " + args.fasta + 
            " -dbtype nucl -out " + args.output_prefix)
        print("The following makeblastdb command will be run:")
        print(cmd)
        ret = subprocess.call(shlex.split(cmd))
        if ret != 0:
            print("Something seems to have gone wrong with makeblastdb!")
    else:
        print("The output files for makeblastdb already exist! Moving on...")
    
    print("Done generating database files!")

if __name__ == '__main__':
    main()
