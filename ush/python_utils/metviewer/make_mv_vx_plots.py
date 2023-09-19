#!/usr/bin/env python3

import os
import sys
import glob
import argparse
import yaml
import re
#import fill_jinja_template
#from socket import socket
from fill_jinja_template import fill_jinja_template

import logging
from textwrap import dedent
from datetime import datetime
from datetime import timedelta

import subprocess

from generate_metviewer_xmls import generate_metviewer_xmls

import sys
from pathlib import Path # if you haven't already done so
file = Path(__file__).resolve()
parent, root = file.parent, file.parents[1]
ushdir = Path(os.path.join(root, '..')).resolve()
#    ushdir=os.path.join(homedir,'ush')
print(f"")
print(f"AAAAAAAAAAAAAAAAAAAAAAAAAAA")
print(f"__file__ = {__file__}")
print(f"parent = {parent}")
print(f"root = {root}")
print(f"ushdir = {ushdir}")
sys.path.append(str(ushdir))

from python_utils import (
    log_info,
    load_config_file,
)


#def load_config_for_setup(ushdir, default_config, user_config):
def load_user_config(ushdir, args):
    """Load in the default, machine, and user configuration files into
    Python dictionaries. Return the combined experiment dictionary.

    Args:
      ushdir             (str): Path to the ush directory for SRW
      default_config     (str): Path to the default config YAML
      user_config        (str): Path to the user-provided config YAML

    Returns:
      Python dict of configuration settings from YAML files.
    """

    logging.basicConfig(level=logging.INFO)
    ## Load the default config.
    #logging.debug(f"Loading config defaults file {default_config}")
    #cfg_d = load_config_file(default_config)
    #logging.debug(f"Read in the following values from config defaults file:\n")
    #logging.debug(cfg_d)

    fcst_init_time_first = '2022050100'
    num_fcsts = 12
    fcst_init_intvl = 24
    fcst_len_hrs = 36
    models = ['href', 'gdas', 'gefs']
    num_ens_mems = [10, 10, 10]
    base_dir = '/home/ketefian/ufs-srweather-app/ush/python_utils/metviewer/mv_output'

    user_config = args.config
    cfg_u = load_config_file(user_config)
    logging.debug(f"Read in the following values from YAML config file {user_config}:\n")
    logging.debug(cfg_u)

    print(f"cfg_u = {cfg_u}")

    for stat, stat_dict in cfg_u.items():

        print(f"")
        print(f"stat = {stat}")
        print(f"stat_dict = {stat_dict}")

        if stat in args.exclude_stats:
            logging.info(f'Skipping plotting of statistic "{stat}"...')
        else:
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

                        args = ['--fcst_init', fcst_init_time_first] \
                             + [str(num_fcsts), str(fcst_init_intvl)] \
                             + ['--fcst_len_hrs', str(fcst_len_hrs), 
                                '--models', ] + models \
                             + ['--num_ens'] + [str(n) for n in num_ens_mems] + \
                               ['--stat', stat,
                                '--fcst_var', fcst_var,
                                '--level_or_accum', level,
                                '--threshold', thresh,
                                '--metviewer_output_dir', base_dir]
                        print(f"      args = {args}")
                        print(f"      CALLING generate ...")
                        generate_metviewer_xmls(args)
                        #generate_metviewer_xmls
                        print(f"      DONE CALLING generate ...")
                        #generate_metviewer_xmls(sys.argv[1:])

#
# -----------------------------------------------------------------------
#
# Call the function defined above.
#
# -----------------------------------------------------------------------
#
if __name__ == "__main__":
    USHdir = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(
        description='Call MetViewer to create vx plots.'
    )

    parser.add_argument('--output_dir',
                        type=str,
                        required=False, default='mv_config.yml',
                        help='Path of directory in which to place MetViewer output')

    parser.add_argument('--config',
                        type=str,
                        required=False, default='config_mv_plots.yml',
                        help='Name of yaml user configuration file for MetViewer plot generation')

    parser.add_argument('--exclude_stats',
                        type=str,
                        required=False, default=None,
                        choices=['auc', 'bias', 'brier', 'fbias', 'rely', 'rhist', 'ss'],
                        help='Stats to exclude from verification plot generation')

    args = parser.parse_args()

    load_user_config(USHdir, args)

