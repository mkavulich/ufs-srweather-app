#!/usr/bin/env python3

import sys
import argparse
import logging
from textwrap import dedent

from python_utils import (
    calculate_core_hours,
    load_config_file,
    monitor_jobs,
    print_WE2E_summary,
    update_expt_status,
    update_expt_status_parallel,
    write_monitor_file
)

from check_python_version import check_python_version


def setup_logging(logfile: str = "log.run_WE2E_tests", debug: bool = False) -> None:
    """
    Sets up logging, printing high-priority (INFO and higher) messages to screen, and printing all
    messages with detailed timing and routine info in the specified text file.
    """
    logging.getLogger().setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(name)-16s %(levelname)-8s %(message)s")

    fh = logging.FileHandler(logfile, mode='a')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logging.getLogger().addHandler(fh)

    logging.debug(f"Finished setting up debug file logging in {logfile}")
    console = logging.StreamHandler()
    if debug:
        console.setLevel(logging.DEBUG)
    else:
        console.setLevel(logging.INFO)
    logging.getLogger().addHandler(console)
    logging.debug("Logging set up successfully")


if __name__ == "__main__":

    check_python_version()

    logfile='log.monitor_jobs'

    #Parse arguments
    parser = argparse.ArgumentParser(description="Script for monitoring and running jobs in a "\
                                                 "specified experiment, as specified in a yaml "\
                                                 "configuration file\n")

    parser.add_argument('-y', '--yaml_file', type=str,
                        help='YAML-format file specifying the information of jobs to be run; '\
                             'for an example file, see monitor_jobs.yaml', required=True)
    parser.add_argument('-p', '--procs', type=int,
                        help='Run resource-heavy tasks (such as calls to rocotorun) in parallel, '\
                             'with provided number of parallel tasks', default=1)
    parser.add_argument('-m', '--mode', type=str, default='continuous',
                        choices=['continuous','advance'],
                        help='continuous: script will run continuously until all experiments are'\
                             'finished.'\
                             'advance: will only advance each experiment one step')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Script will be run in debug mode with more verbose output. ' +
                             'WARNING: increased verbosity may run very slow on some platforms')

    args = parser.parse_args()

    setup_logging(logfile,args.debug)

    logging.debug(f"Loading configure file {args.yaml_file}")
    expts_dict = load_config_file(args.yaml_file)

    if args.procs < 1:
        raise ValueError('You can not have less than one parallel process; select a valid value for --procs')

    #Call main function

    try:
        monitor_jobs(expts_dict=expts_dict,monitor_file=args.yaml_file,procs=args.procs,
                     mode=args.mode,debug=args.debug)
    except KeyboardInterrupt:
        logging.info("\n\nUser interrupted monitor script; to resume monitoring jobs run:\n")
        logging.info(f"{__file__} -y={args.yaml_file} -p={args.procs}\n")
    except:
        logging.exception(
            dedent(
                f"""
                *********************************************************************
                FATAL ERROR:
                An error occurred. See the error message(s) printed below.
                For more detailed information, check the log file from the workflow
                generation script: {logfile}
                *********************************************************************\n
                """
            )
        )
