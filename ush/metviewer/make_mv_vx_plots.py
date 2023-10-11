#!/usr/bin/env python3

import os
import sys
import glob
import argparse
import yaml

import logging
import textwrap
from textwrap import dedent

import pprint
import subprocess

from plot_vx_metviewer import plot_vx_metviewer
from plot_vx_metviewer import get_pprint_str

from pathlib import Path
file = Path(__file__).resolve()
ush_dir = file.parents[1]
sys.path.append(str(ush_dir))

from python_utils import (
    log_info,
    load_config_file,
)


def make_mv_vx_plots(args):
    """Make multiple verification plots using MetViewer and the settings
    file specified as part of args.

    Arguments:
      args:  Dictionary of arguments.
    """

    # Set up logging.
    # If the name/path of a log file has been specified in the command line arguments,
    # place the logging output in it (existing log files of the same name are overwritten).
    # Otherwise, direct the output to the screen.
    log_level = str.upper(args.log_level)
    FORMAT = "[%(levelname)s:%(name)s:  %(filename)s, line %(lineno)s: %(funcName)s()] %(message)s"
    if args.log_fp:
        logging.basicConfig(level=log_level, format=FORMAT, filename=args.log_fp, filemode='w')
    else:
        logging.basicConfig(level=log_level, format=FORMAT)

    config_fp = args.config_fp
    config_dict = load_config_file(config_fp)
    logging.info(dedent(f"""
        Reading in configuration file {config_fp} ...
        """))

    fcst_init_info = config_dict['fcst_init_info']
    fcst_init_info = map(str, list(fcst_init_info.values()))
    # fcst_init_info is a list containing both strings and integers.  For use below,
    # convert it to a list of strings only.
    fcst_init_info = [str(elem) for elem in fcst_init_info]

    fcst_len_hrs = str(config_dict['fcst_len_hrs'])
    mv_database_name = config_dict['mv_database_name']
    model_names = config_dict['model_names']

    # Keep track of the number of times the script that generates a 
    # MetViewer xml and calls MetViewer is called.  This can then be
    # compared to the number of plots (png files) generated to see
    # if any are missing/failed.
    num_mv_calls = 0

    vx_stats_dict = config_dict["vx_stats"]
    for stat, stat_dict in vx_stats_dict.items():

        if stat in args.exclude_stats:
            logging.info(dedent(f"""\n
                Skipping plotting of statistic "{stat}" because it is in the list of 
                stats to exclude ...
                  args.exclude_stats = {args.exclude_stats}
                """))

        elif (not args.include_stats) or (args.include_stats and stat in args.include_stats):
            logging.info(dedent(f"""
                Plotting statistic "{stat}" for various forecast variables ...
                """))
            logging.debug(f"""\nstat_dict =\n{get_pprint_str(stat_dict, '  ')}\n""")

            for fcst_var, fcst_var_dict in stat_dict.items():

                logging.info(dedent(f"""
                    Plotting statistic "{stat}" for forecast variable "{fcst_var}" at various levels ...
                    """))
                logging.debug(f"""\nfcst_var_dict =\n{get_pprint_str(fcst_var_dict, '  ')}\n""")

                for level, level_dict in fcst_var_dict.items():
                    logging.info(dedent(f"""
                        Plotting statistic "{stat}" for forecast variable "{fcst_var}" at level "{level}" ...
                        """))
                    logging.debug(f"""\nlevel_dict =\n{get_pprint_str(level_dict, '  ')}\n""")

                    thresholds = level_dict['thresholds']
                    for thresh in thresholds:
                        logging.info(dedent(f"""
                            Plotting statistic "{stat}" for forecast variable "{fcst_var}" at level "{level}"
                            and threshold "{thresh}" (threshold may be empty for certain stats) ...
                            """))

                        args_list = ['--mv_database_name', mv_database_name, \
                                     '--model_names', ] + model_names \
                                  + ['--vx_stat', stat,
                                     '--fcst_init_info'] + fcst_init_info \
                                  + ['--fcst_len_hrs', fcst_len_hrs, 
                                     '--fcst_var', fcst_var,
                                     '--level_or_accum', level,
                                     '--threshold', thresh, 
                                     '--mv_output_dir', args.output_dir]

                        logging.debug(f"""\nArgument list passed to plotting script is:\nargs_list =\n{get_pprint_str(args_list, '  ')}\n""")

                        num_mv_calls += 1
                        logging.debug(dedent(f"""
                            Calling MetViewer plotting script ...
                              num_mv_calls = {num_mv_calls}
                            """))
                        plot_vx_metviewer(args_list)
                        logging.debug(dedent(f"""
                            Done calling MetViewer plotting script.
                            """))

    logging.info(dedent(f"""
        Total number of calls to MetViewer plotting script:
          num_mv_calls = {num_mv_calls}
        """))
#
# -----------------------------------------------------------------------
#
# Call the function defined above.
#
# -----------------------------------------------------------------------
#
if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='Call MetViewer to create vx plots.'
    )

    # Find the path to the directory containing the clone of the SRW App.  The index of
    # .parents will have to be changed if this script is moved elsewhere in the SRW App's
    # directory structure.
    crnt_script_fp = Path(__file__).resolve()
    home_dir = crnt_script_fp.parents[2]
    expts_dir = Path(os.path.join(home_dir, '../expts_dir')).resolve()
    parser.add_argument('--output_dir',
                        type=str,
                        required=False, default=os.path.join(expts_dir, 'mv_output'),
                        help=dedent(f'''Directory in which to place output files (generated xmls,
                                        MetViewer generated plots and other files, etc).  These
                                        will usually be placed in subdirectories under this 
                                        output directory.'''))

    parser.add_argument('--config_fp',
                        type=str,
                        required=False, default='config_mv_plots.default.yml',
                        help=dedent(f'''Name of or path (absolute or relative) to yaml user
                                        plot configuration file for MetViewer plot generation.'''))

    parser.add_argument('--log_fp',
                        type=str,
                        required=False, default='',
                        help=dedent(f'''Name of or path (absolute or relative) to log file.  If 
                                        not specified, the output goes to screen.'''))

    choices_log_level = [pair for lvl in list(logging._nameToLevel.keys())
                              for pair in (str.lower(lvl), str.upper(lvl))]
    parser.add_argument('--log_level',
                        type=str,
                        required=False, default='info',
                        choices=choices_log_level,
                        help=dedent(f'''Logging level to use with the logging" module.'''))

    parser.add_argument('--include_stats', nargs='+',
                        type=str.lower,
                        required=False, default=[],
                        choices=['auc', 'bias', 'brier', 'fbias', 'rely', 'rhist', 'ss'],
                        help=dedent(f'''Stats to include in verification plot generation.  A stat
                                        included here will still be excluded if it is not in the
                                        yaml user plot configuration file.'''))

    parser.add_argument('--exclude_stats', nargs='+',
                        type=str.lower,
                        required=False, default=[],
                        choices=['auc', 'bias', 'brier', 'fbias', 'rely', 'rhist', 'ss'],
                        help='Stats to exclude from verification plot generation.')

    args = parser.parse_args()

    make_mv_vx_plots(args)

