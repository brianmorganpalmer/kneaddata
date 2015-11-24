import os
import sys
import shlex
import logging
import tempfile
import gzip
import re
import logging

from math import floor
from functools import partial
from contextlib import contextmanager
from multiprocessing import cpu_count

# name global logging instance
logger=logging.getLogger(__name__)

def divvy_threads(args):
    avail_cpus = args.threads or cpu_count()-1
    n_consumers = len(args.reference_db)
    trim_threads = 1
    if n_consumers > 0:
        align_threads = max(1, floor(avail_cpus/float(n_consumers)))
    else:
        align_threads = 1
    return int(trim_threads), int(align_threads)
    

def try_create_dir(d):
    if not os.path.exists(d):
        logging.warning("Directory `%s' doesn't exist. Creating.", d)
        try:
            os.makedirs(d)
        except Exception as e:
            logging.crit("Unable to create directory `%s': %s", d, str(e))
            sys.exit(1)


@contextmanager
def mktempfifo(names=("a",)):
    tmpdir = tempfile.mkdtemp()
    names = map(partial(os.path.join, tmpdir), names)
    map(os.mkfifo, names)
    try:
        yield names
    finally:
        # still perform cleanup even if there were exceptions/errors in the
        # "with" block
        map(os.remove, names)
        os.rmdir(tmpdir)


@contextmanager
def mkfifo_here(names=("a",), mode=0600):
    for n in names:
        os.mkfifo(n, mode)
    try:
        yield names
    finally:
        for n in names:
            os.remove(n)


def process_return(name, retcode, stdout, stderr):
    if name:
        logging.debug("Finished running %s!" %name)
    if retcode:
        log = logging.critical
        log("%s exited with exit status %d", name, retcode)
    else:
        log = logging.debug
    if stdout:
        log("%s stdout:\n%s", name, stdout)
    if stderr:
        log("%s stderr:\n%s", name, stderr)
    if retcode:
        sys.exit(retcode)


def parse_positive_int(string):
    try:
        val = int(string)
    except ValueError:
        raise argparse.ArgumentTypeError("Unable to parse %s to int" %string) 
    if val <= 0:
        raise argparse.ArgumentTypeError("%s is not a positive integer" %string)
    return val


def _get_bowtie2_args(bowtie2_args):
    for arg in map(shlex.split, bowtie2_args):
        for a in arg:
            yield a
            
def get_file_format(file):
    """ Determine the format of the file """

    format="unknown"
    file_handle=None

    # check the file exists and is readable
    if not os.path.isfile(file):
        logging.critical("The input file selected is not a file: %s.",file)

    if not os.access(file, os.R_OK):
        logging.critical("The input file selected is not readable: %s.",file)

    try:
        # check for gzipped files
        if file.endswith(".gz"):
            file_handle = gzip.open(file, "r")
        else:
            file_handle = open(file, "r")

        first_line = file_handle.readline()
        second_line = file_handle.readline()
    except EnvironmentError:
        # if unable to open and read the file, return unknown
        return "unknown"
    finally:
        if file_handle:
            file_handle.close()

    # check that second line is only nucleotides or amino acids
    if re.search("^[A-Z|a-z]+$", second_line):
        # check first line to determine fasta or fastq format
        if re.search("^@",first_line):
            format="fastq"
        if re.search("^>",first_line):
            format="fasta"

    return format

def is_file_fastq(file):
    """ Return true if the file is fastq """
    
    if get_file_format(file) == "fastq":
        return True
    else:
        return False


def log_run_and_arguments(executable, arguments, verbose):
    """ Log the run and arguments and print messages """
    
    message="Running "+executable+" ..."
    print(message)
    logger.info(message)
    # log the executable and arguments
    message=executable+" " + " ".join(arguments)
    if verbose:
        print(message)
    logger.debug(message)
    
def count_reads_in_fastq_file(file,verbose):
    """ Count the number of reads in a fastq file """
    
    total_lines=0
    try:
        # file is compressed based on extension
        if file.endswith(".gz"):
            file_handle=gzip.open(file)
        else:
            file_handle=open(file)
            
        # count the lines in the file
        for line in file_handle:
            total_lines+=1
            
        file_handle.close()
    except EnvironmentError:
        total_lines=0
        message="Unable to count reads in file: "+file
        if verbose:
            print(message)
        logger.debug(message)
        
    # divide the total line number to get the total number of reads
    total_reads=total_lines/4
    
    return total_reads

def log_reads_in_files(files,message_base,verbose=None):
    """ Log the number of reads in the files """
        
    for file in files:
        total_reads=count_reads_in_fastq_file(file,verbose)
        message=message_base+" ( "+file+" ): " + str(total_reads)
        logger.info(message)
        print(message)
        
def find_exe_in_path(exe, bypass_permissions_check=None):
    """
    Check that an executable exists in $PATH
    """
    
    paths = os.environ["PATH"].split(os.pathsep)
    for path in paths:
        fullexe = os.path.join(path,exe)
        if os.path.exists(fullexe):
            if bypass_permissions_check or os.access(fullexe,os.X_OK):
                return path
    return None
        
def find_dependency(path_provided,exe,name,path_option,bypass_permissions_check):
    """ 
    Check if the dependency can be found in the path provided or in $PATH
    Return the location of the dependency
    """

    if path_provided:
        path_provided=os.path.abspath(path_provided)
        # check that the exe can be found
        try:
            files=os.listdir(path_provided)
        except EnvironmentError:
            sys.exit("ERROR: Unable to list files in "+name+" directory: "+ path_provided)
            
        if not exe in files:
            sys.exit("ERROR: The "+exe+" executable is not included in the directory: " + path_provided)
        else:
            found_path=path_provided
    else:
        # search for the exe
        exe_path=find_exe_in_path(exe, bypass_permissions_check)
        if not exe_path:
            sys.exit("ERROR: Unable to find "+name+". Please provide the "+
                "full path to "+name+" with "+path_option+".")
        else:
            found_path=exe_path  
        
    return os.path.abspath(os.path.join(found_path,exe))

def find_bowtie2_index(directory):
    """
    Search through the directory for the name of the bowtie2 index files
    Or if a file name is provided check it is a bowtie2 index
    """
    
    index=""
    # the extensions for standard bowtie2 index files
    bowtie2_index_ext_list=[".1.bt2",".2.bt2",".3.bt2",".4.bt2",
        ".rev.1.bt2",".rev.2.bt2"]
    # an extension for one of the index files for a large database
    bowtie2_large_index_ext=".1.bt2l"
    
    bowtie2_extensions=bowtie2_index_ext_list+[bowtie2_large_index_ext]
    
    if not os.path.isdir(directory):
        # check if this is the bowtie2 index file
        if os.path.isfile(directory):
            # check for the bowtie2 extension
            for ext in bowtie2_extensions:
                if re.search(ext+"$",directory):
                    index=directory.replace(ext,"")
                    break
        else:
            # check if this is the basename of the bowtie2 index files
            small_index=directory+bowtie2_index_ext_list[0]
            large_index=directory+bowtie2_large_index_ext
            if os.path.isfile(small_index) or os.path.isfile(large_index):
                index=directory
    else:
        # search through the files to find one with the bowtie2 extension
        for file in os.listdir(directory):
            # look for an extension for a standard and large bowtie2 indexed database
            for ext in [bowtie2_index_ext_list[-1],bowtie2_large_index_ext]:
                if re.search(ext+"$",file):
                    index=os.path.join(directory,file.replace(ext,""))
                    break
            if index:
                break
    
    if not index:
        sys.exit("ERROR: Unable to find bowtie2 index files in directory: " + directory)
    
    return index

    