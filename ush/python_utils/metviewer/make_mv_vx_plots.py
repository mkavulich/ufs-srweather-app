#!/usr/bin/env python3

import os
import sys
import glob
import argparse
import yaml
import re

import logging
from textwrap import dedent
from datetime import datetime
from datetime import timedelta

import subprocess

from plot_vx_metviewer import plot_vx_metviewer

import sys
from pathlib import Path
file = Path(__file__).resolve()
parent, root = file.parent, file.parents[1]
ush_dir = Path(os.path.join(root, '..')).resolve()
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

    logging.basicConfig(level=logging.INFO)

    config_fn = args.config
    config_dict = load_config_file(config_fn)
    logging.info(dedent(f"""
        Reading in configuration file {config_fn} ...
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

        print(f"")
        print(f"stat = {stat}")
        print(f"stat_dict = {stat_dict}")

        if stat in args.exclude_stats:
            #logging.info(f'Skipping plotting of statistic "{stat}"...')
            print(f"")
            print(f'Skipping plotting of statistic "{stat}"...')

        elif (not args.include_stats) or (args.include_stats and stat in args.include_stats):
            #logging.info(f'NOT skipping plotting of statistic "{stat}"...')
            print(f"")
            print(f'NOT skipping plotting of statistic "{stat}"...')

            print(f"")
            print(f"  stat = {stat}")
            print(f"  stat_dict = {stat_dict}")
            print(f"  args.include_stats = {args.include_stats}")
            print(f"  stat in args.include_stats = {stat in args.include_stats}")

            for fcst_var, fcst_var_dict in stat_dict.items():

                print(f"")
                print(f"  fcst_var = {fcst_var}")
                print(f"  fcst_var_dict = {fcst_var_dict}")

                for level, level_dict in fcst_var_dict.items():
                    print(f"")
                    print(f"    level = {level}")
                    print(f"    level_dict = {level_dict}")

                    thresholds = level_dict['thresholds']
#                    print(f"      thresholds = {thresholds}")
                    for thresh in thresholds:
                        print(f"      thresh = {thresh}")

                        args_list = ['--mv_database_name', mv_database_name, \
                                     '--model_names', ] + model_names \
                                  + ['--vx_stat', stat,
                                     '--fcst_init_info'] + fcst_init_info \
                                  + ['--fcst_len_hrs', fcst_len_hrs, 
                                     '--fcst_var', fcst_var,
                                     '--level_or_accum', level,
                                     '--threshold', thresh, 
                                     '--mv_output_dir', args.output_dir]
                        print(f"      args_list = {args_list}")
                        num_mv_calls += 1
                        print(f"=====>>>>> num_mv_calls = {num_mv_calls}")
                        print(f"      CALLING MetViewer plotting script...")
                        plot_vx_metviewer(args_list)
                        print(f"      DONE CALLING MetViewer plotting script...")

    print(f"")
    print(f"num_mv_calls = {num_mv_calls}")
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

    crnt_script_fp = Path(__file__).resolve()
    home_dir = crnt_script_fp.parents[3]
    expts_dir = Path(os.path.join(home_dir, '../expts_dir')).resolve()
    parser.add_argument('--output_dir',
                        type=str,
                        required=False, default=os.path.join(expts_dir, 'mv_output'),
                        help='Directory in which to place MetViewer output')

    parser.add_argument('--config',
                        type=str,
                        required=False, default='config_mv_plots.default.yml',
                        help='Name of yaml user configuration file for MetViewer plot generation')

    parser.add_argument('--include_stats', nargs='+',
                        type=str.lower,
                        required=False, default=[],
                        choices=['auc', 'bias', 'brier', 'fbias', 'rely', 'rhist', 'ss'],
                        help=dedent(f'''Stats to include in verification plot generation.  A stat
                                        included here will still be excluded if it is not in the
                                        yaml configuration file.'''))

    parser.add_argument('--exclude_stats', nargs='+',
                        type=str.lower,
                        required=False, default=[],
                        choices=['auc', 'bias', 'brier', 'fbias', 'rely', 'rhist', 'ss'],
                        help='Stats to exclude from verification plot generation')

    args = parser.parse_args()

    make_mv_vx_plots(args)

