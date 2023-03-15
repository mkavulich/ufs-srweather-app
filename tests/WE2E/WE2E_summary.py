#!/usr/bin/env python3

import sys
import argparse
import logging

sys.path.append("../../ush")

from python_utils import load_config_file

from check_python_version import check_python_version

from utils import calculate_core_hours, create_expts_dict, print_WE2E_summary, write_monitor_file

def WE2E_summary(args):
    yaml_file = args.yaml_file

    # Set up dictionary of experiments
    if args.expt_dir:
        yaml_file, expts_dict = create_expts_dict(args.expt_dir)
    elif args.yaml_file:
        expts_dict = load_config_file(args.yaml_file)
    else:
        raise ValueError(f'Bad arguments; run {__file__} -h for more information')

    # Calculate core hours and update yaml
    calculate_core_hours(expts_dict)
    write_monitor_file(yaml_file,expts_dict)

    #Call function to print summary
    print_WE2E_summary(expts_dict, args.debug)


def setup_logging(debug: bool = False) -> None:
    """
    Sets up logging, printing high-priority (INFO and higher) messages to screen, and printing all
    messages with detailed timing and routine info in the specified text file.
    """
    logging.getLogger().setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    if debug:
        console.setLevel(logging.DEBUG)
    else:
        console.setLevel(logging.INFO)
    logging.getLogger().addHandler(console)
    logging.debug("Logging set up successfully")



if __name__ == "__main__":

    check_python_version()

    #Parse arguments
    parser = argparse.ArgumentParser(
                     description="Script for creating a job summary printed to screen and a file, "\
                     "either from a yaml experiment file created by monitor_jobs() or from a "\
                     "provided directory of experiments\n")

    req = parser.add_mutually_exclusive_group(required=True)
    req.add_argument('-y', '--yaml_file', type=str,
                     help='YAML-format file specifying the information of jobs to be summarized; '\
                          'for an example file, see WE2E_tests.yaml')
    req.add_argument('-e', '--expt_dir', type=str,
                     help='The full path of an experiment directory, containing one or more '\
                          'subdirectories with UFS SRW App experiments in them')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Script will be run in debug mode with more verbose output')

    args = parser.parse_args()

    setup_logging(args.debug)

    WE2E_summary(args)
