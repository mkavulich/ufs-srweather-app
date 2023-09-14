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

#sys.path.insert(1, "./ush")
#
#from generate_FV3LAM_wflow import generate_FV3LAM_wflow
#from python_utils import (
#    cfg_to_yaml_str,
#    load_config_file,
#)
#
#from check_python_version import check_python_version
#
#from monitor_jobs import monitor_jobs, write_monitor_file
#from utils import print_test_info

#def run_we2e_tests(homedir, args) -> None:
#    """Function to run the WE2E tests selected by the user
#
#    Args:
#        homedir (str): The full path of the top-level app directory
#        args    (obj): The argparse.Namespace object containing command-line arguments
#
#    Returns:
#        None
#    """
#
#    # Set some important directories
#    ushdir=os.path.join(homedir,'ush')
#
#    # Set some variables based on input arguments
#    run_envir = args.run_envir
#    machine = args.machine.lower()


if __name__ == "__main__":

    # Check python version and presence of some non-standard packages
    #check_python_version()

    #Get the "Home" directory, two levels above this one
    homedir=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logfile='log.run_WE2E_tests'

    #console_handler = logging.getLogger().handlers[1]
    #console_handler.setLevel(logging.WARNING)
    logging.basicConfig(level=logging.INFO)

    # These are incorrect, need to fix!!
    xml_colors = {'red': '#ff0000FF',
                  'blue': '#8a2be2FF',
                  'green': '#32cd32FF'}
    choices_colors = list(xml_colors.keys())
    #num_colors_max = len(choices_colors)
    #print(f"")
    #print(f"AAAAAAAAAAAAAAAAAAAAAAAAAAA")
    #print(f"num_colors_max = {num_colors_max}")
    #lkjlkj

    stat_long_names = {'auc': 'Area Under the Curve',
                       'bias': 'Bias',
                       'brier': 'Brier Score',
                       'fbias': 'Frequency Bias',
                       'rely': 'Reliability',
                       'rhist': 'Rank Histogram',
                       'ss': 'Spread-Skill Ratio'}
    choices_stats = sorted(list(stat_long_names.keys()))

    fcst_var_long_names = {'apcp': 'Accumulated Precipitation',
                           'cape': 'Convenctive Available Potential Energy',
                           'dpt': 'Dew Point Temperature',
                           'hgt': 'Height',
                           'refc': 'Composite Reflectivity',
                           'tmp': 'Temperature',
                           'wind': 'Wind'}
    choices_fcst_vars = sorted(list(fcst_var_long_names.keys()))

    #Parse arguments
    parser = argparse.ArgumentParser(epilog="For more information about config arguments (denoted "\
                                            "in CAPS), see ush/config_defaults.yaml\n")
    # Create a group for optional arguments so they can be listed after required args
    optional = parser._action_groups.pop()
    required = parser.add_argument_group('required arguments')


    model_names_in_database = {'gdas': 'RRFS_GDAS_GF.SPP.SPPT',
                               'gefs': 'RRFS_GEFS_GF.SPP.SPPT',
                               'href': 'HREF'}
    choices_models = sorted(list(model_names_in_database.keys()))
    required.add_argument('-m', '--models', nargs='+',
                          type=str.lower,
                          required=True,
                          choices=choices_models,
                          help='Names of models to include')

    required.add_argument('-n', '--num_ens_mems', nargs='+',
                          type=int,
                          required=True,
                          help='Number of ensemble members per model (all have same number of members if only one spcified)')

    required.add_argument('-c', '--colors', nargs='+',
                          type=int,
                          required=False, default=choices_colors,
                          choices=choices_colors,
                          help='Line color of each model')

    required.add_argument('-s', '--stat',
                          type=str.lower,
                          required=True,
                          choices=choices_stats,
                          help='Name of verification statistic/metric')

    required.add_argument('-i', '--incl_ens_means',
                          required=False, action=argparse.BooleanOptionalAction, default=argparse.SUPPRESS,
                          help='Flag for including ensemble mean curves in plot')
#
# Note:
# * BIAS, RHST, SS dont use thresholds.
# * AUC, BRIER, FBIAS, RELY use thresholds.
#
# For BIAS, RHST, and SS:
# ======================
# fcst_var    level_or_accum             threshold    stat types
# --------    --------------             ---------    ----------
# apcp        03hr, 06hr                 none         RHST, SS
# cape        ??                         none         RHST
# dpt         2m                         none         BIAS, RHST, SS
# hgt         500mb                      none         RHST, SS
# refc        L0 (BIAS only)             none         BIAS, RHST, SS
# tmp         2m, 500mb, 700mb, 850mb    none         BIAS, RHST, SS
# wind        500mb, 700mb, 850mb        none         BIAS, RHST, SS
#
# For AUC, BRIER, FBIAS, and RELY:
# ===============================
# fcst_var    level_or_accum    threshold
# --------    --------------    ---------
# apcp        03hr              gt0.0mm (AUC,BRIER,FBIAS,RELY), ge2.54mm (AUC,BRIER,FBIAS,RELY)
# dpt         2m                ge288K (AUC,BRIER,RELY), ge293K (AUC,BRIER)
# refc        L0                ge20dBZ (AUC,BRIER,FBIAS,RELY), ge30dBZ (AUC,BRIER,FBIAS,RELY), ge40dBZ (AUC,BRIER,FBIAS,RELY), ge50dBZ (AUC,BRIER,FBIAS)
# tmp         2m, 850mb         ge288K (AUC,BRIER,RELY), ge293K (AUC,BRIER,RELY), ge298K (AUC,BRIER,RELY), ge303K (RELY)
# wind        10m, 700mb        ge5ms (AUC,BRIER,RELY), ge10ms (AUC,BRIER,RELY)
#
    required.add_argument('-f', '--fcst_var',
                          type=str.lower,
                          required=True, 
                          choices=choices_fcst_vars,
                          help='Name of forecast variable to verify')

    required.add_argument('--fcst_init', nargs=3,
                          type=str,
                          required=True, 
                          help='Initialization time of first forecast (in YYYYMMDDHH), number of forecasts, and forecast initialization interval (in HH)')

    # Define dictionary containing the valid levels/accumulations for 
    # each valid forecast variable.
    valid_levels_or_accums_by_fcst_var = {
        'apcp': ['3h', '3hr', '03h', '03hr',
                 '6h', '6hr', '06h', '06hr', ],
        'cape': [''],
        'dpt': ['2m', '02m'],
        'hgt': ['500mb'],
        'refc': ['L0'],
        'tmp': ['2m', '02m', '500mb', '700mb', '850mb'],
        'wind': ['10m', '500mb', '700mb', '850mb']
        }
    # Use the dictionary of valid levels/accumulations defined above to
    # create a list of valid values for the level/accumulation argument.
    # Note that this list does not contain duplicates and is sorted for
    # clarity.
    choices_level_or_accum = [item for sublist in valid_levels_or_accums_by_fcst_var.values() for item in sublist]
    choices_level_or_accum = sorted(list(set(choices_level_or_accum)))

    required.add_argument('-l', '--level_or_accum',
                          type=str,
                          required=False,
                          choices=choices_level_or_accum,
                          help='Vertical level or accumulation period')

    valid_thresholds_by_fcst_var = {
        'apcp': ['gt0.0mm', 'ge2.54mm'],
        'dpt': ['ge288K', 'ge293K'],
        'refc': ['ge20dBZ', 'ge30dBZ', 'ge40dBZ', 'ge50dBZ'],
        'tmp': ['ge288K', 'ge293K', 'ge298K', 'ge303K'],
        'wind': ['ge5ms', 'ge10ms'],
        }
    choices_thresholds = [item for sublist in valid_thresholds_by_fcst_var.values() for item in sublist]
    choices_thresholds = sorted(list(set(choices_thresholds)))

    required.add_argument('-t', '--threshold',
                          type=str,
                          required=False, default='',
                          choices=choices_thresholds,
                          help='Threshold')

    required.add_argument('-r', '--fcst_len_hrs',
                          type=int,
                          required=True,
                          help='Forecast length (in integer hours)')

    required.add_argument('-d', '--database',
                          type=str,
                          required=False, default='mv_gefs_gdas_rtps_href_spring_2022', 
                          help='Name of METViewer database')


    parser._action_groups.append(optional)

    args = parser.parse_args()

    print(f"")
    print(f"AAAAAAAAAAAAAAAAAAAAAAAAAAA")
    print(f"args = {args}")
    print(f"type(args) = {type(args)}")
    print(f"args.fcst_init = {args.fcst_init}")

    #aaa = datetime.strptime('2005051602', '%Y%m%d%H')
    fcst_init_time_first = datetime.strptime(args.fcst_init[0], '%Y%m%d%H')
    #fcst_init_last = datetime.strptime(args.fcst_init[1], '%Y%m%d%H')
    num_fcsts = int(args.fcst_init[1])
    fcst_init_intvl = timedelta(hours=int(args.fcst_init[2]))
    #num_fcsts = 12
    print(f"")
    print(f"fcst_init_time_first = {fcst_init_time_first}")
    #print(f"type(fcst_init_first) = {type(fcst_init_first)}")
    #print(f"fcst_init_last = {fcst_init_last}")
    print(f"num_fcsts = {num_fcsts}")
    print(f"fcst_init_intvl = {fcst_init_intvl}")
    #aaa = fcst_init_last - fcst_init_first
    #print(f"")
    #print(f"aaa = {aaa}")
    #print(f"type(aaa) = {type(aaa)}")
    #bbb = (aaa/fcst_init_intvl) % 1.0
    #print(f"")
    #print(f"bbb = {bbb}")
    #print(f"type(bbb) = {type(bbb)}")
    fcst_init_times = list(range(0,num_fcsts))
    print(f"")
    print(f"fcst_init_times = {fcst_init_times}")
    fcst_init_times = [fcst_init_time_first + i*fcst_init_intvl for i in fcst_init_times]
#list2 = [x for ind, x in enumerate(list1) if 4 > ind > 0]
    print(f"")
    print(f"fcst_init_times = {fcst_init_times}")
    fcst_init_times = [i.strftime("%Y-%m-%d %H:%M:%S") for i in fcst_init_times]
    #my_list = my_list.strftime()
#date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
    print(f"")
    print(f"fcst_init_times = {fcst_init_times}")

    #jkjkjkjkjkjkj

    if ('incl_ens_means' not in args):
        incl_ens_means = False
        if (args.stat == 'bias'): incl_ens_means = True
    else:
        incl_ens_means = args.incl_ens_means
    # Apparently we can just reset or create incl_ens_means within the args Namespace
    # as follows:
    args.incl_ens_means = incl_ens_means

    valid_levels_or_accums = valid_levels_or_accums_by_fcst_var[args.fcst_var]
    if args.level_or_accum not in valid_levels_or_accums:
        logging.error(dedent(f"""
            The specified level or accumulation is not compatible with the specified forecast variable:
              fcst_var = {args.fcst_var}
              level_or_accum = {args.level_or_accum}
            Valid options for level or accumulation for this forecast variable are:
              {valid_levels_or_accums}
            """))
        # Need proper exit here!
        opopopopoipo

    loa = re.findall(r'(\d*\.*\d+)([A-Za-z]+)', args.level_or_accum)
    if loa:
        logging.info(dedent(f"""
            Parsing specified level or accumulation...
            """))
        loa_value, loa_units = list(loa[0])
    else:
        loa_value = ''
        loa_units = ''

    loa_value_no0pad = loa_value.lstrip('0')
    width_0pad = 0
    if loa_units in ['m']:
        width_0pad = 2
    elif loa_units == 'mb':
        width_0pad = 3
    elif loa_units in ['h', 'hr']:
        width_0pad = 2
    loa_value_0pad = loa_value_no0pad.zfill(width_0pad)

    logging.info(dedent(f"""
        Level or accumulation parameters are set as follows:
          loa_value = {loa_value}
          loa_value_no0pad = {loa_value_no0pad}
          loa_value_0pad = {loa_value_0pad}
          loa_units = {loa_units}
        """))
    #adfkjkjkj

    # This can be cleaned up...
    #level_or_accum_mv = args.level_or_accum
    #if args.level_or_accum == '2m' :
    #    level_or_accum_mv = 'Z2'
    #elif args.level_or_accum == '10m':
    #    level_or_accum_mv = 'Z10'
    #elif args.level_or_accum == '500mb':
    #    level_or_accum_mv = 'P500'
    #elif args.level_or_accum == '700mb':
    #    level_or_accum_mv = 'P700'
    #elif args.level_or_accum == '850mb':
    #    level_or_accum_mv = 'P850'
    #elif args.level_or_accum == '01h':
    #    level_or_accum_mv = 'A1'
    #elif args.level_or_accum == '03h':
    #    level_or_accum_mv = 'A3'
    #elif args.level_or_accum == '06h':
    #    level_or_accum_mv = 'A6'
    #elif args.level_or_accum == '24h':
    #    level_or_accum_mv = 'A24'
    # Name for the level or accumulation that MetViewer understands.
    level_or_accum_mv = args.level_or_accum
    if loa_units == 'm':
        level_or_accum_mv = ''.join(['Z', loa_value_no0pad])
    elif loa_units == 'mb':
        level_or_accum_mv = ''.join(['P', loa_value_no0pad])
    elif loa_units in ['h', 'hr']:
        level_or_accum_mv = ''.join(['A', loa_value_no0pad])


    # List of verification stats for which a threshold is not needed.
    no_thresh_stats = ['bias', 'rhist', 'ss']
    # List of verification stats for which a threshold must be specified.
    thresh_stats = [s for s in choices_stats if s not in no_thresh_stats]

    if (args.stat in no_thresh_stats) and (args.threshold):
        no_thresh_stats_fmt_str = ",\n".join("              {!r}: {!r}".format(k, v) for k, v in stat_long_names.items() if k in no_thresh_stats).lstrip()
        logging.info(dedent(f"""
            A threshold is not needed when working with one of the following verification stats:
              {no_thresh_stats_fmt_str}
            Thus, the threshold specified in the argument list ("{args.threshold}") will be reset to an empty string.
            """))
        args.threshold = ''

    elif (args.stat in thresh_stats):
        valid_thresholds = valid_thresholds_by_fcst_var[args.fcst_var]
        if args.threshold not in valid_thresholds:
            logging.error(dedent(f"""
                The specified threshold is not compatible with the specified forecast variable:
                  fcst_var = {args.fcst_var}
                  threshold = {args.threshold}
                Valid options for threshold for this forecast variable are:
                  {valid_thresholds}
                """))
            # Need proper exit here!
            bnkjy

    threshold = re.findall(r'([A-Za-z]+)(\d*\.*\d+)([A-Za-z]+)', args.threshold)
    if threshold:
        logging.info(dedent(f"""
            Parsing specified threshold to obtain comparison operator, value, and units...
            """))
        thresh_comp_oper, thresh_value, thresh_units = list(threshold[0])

        if thresh_comp_oper[0] == 'l': 
            xml_threshold = '&lt;'
        elif thresh_comp_oper[0] == 'g': 
            xml_threshold = '&gt;'

        if thresh_comp_oper[1] == 'e': 
            xml_threshold = "".join([xml_threshold, '='])

        xml_threshold = "".join([xml_threshold, thresh_value])

    else:
        thresh_comp_oper = ''
        thresh_value = ''
        thresh_units = ''
        xml_threshold = ''

    logging.info(dedent(f"""
        Threshold parameters are set as follows:
          thresh_comp_oper = {thresh_comp_oper}
          thresh_value = {thresh_value}
          thresh_units = {thresh_units}
          xml_threshold = {xml_threshold}
        """))

    level_or_accum_str = args.level_or_accum
    if level_or_accum_str == 'L0': level_or_accum_str = ''
    plot_title = " ".join(filter(None,
                          [stat_long_names[args.stat], 'for',
                           level_or_accum_str, fcst_var_long_names[args.fcst_var],
                           xml_threshold, thresh_units]))
    #var_lvl_thresh_str = ''.join(filter(None,
    #                        [args.fcst_var.upper(), level_or_accum_str,
    #                         thresh_comp_oper, thresh_value]))
    var_lvl_str = ''.join(filter(None, [args.fcst_var.upper(), level_or_accum_str]))
    thresh_str = ''.join(filter(None, [thresh_comp_oper, thresh_value, thresh_units]))
    var_lvl_thresh_str = '_'.join(filter(None, [var_lvl_str, thresh_str]))

    models_str = '_'.join(args.models)
    job_title = '_'.join([args.stat, var_lvl_thresh_str, models_str])

    logging.info(dedent(f"""
        Various auxiliary string values:
          level_or_accum_str = {level_or_accum_str}
          plot_title = {plot_title}
          var_lvl_str = {var_lvl_str}
          thresh_str = {thresh_str}
          var_lvl_thresh_str = {var_lvl_thresh_str}
          job_title = {job_title}
          models_str = {models_str}
        """))

    print(f"")
    print(f"AAAAAAAAAAAAAAAAAAAAAAAAAAA")
    print(f"args.models = {args.models}")

    num_models = len(args.models)
    print(f"")
    print(f"AAAAAAAAAAAAAAAAAAAAAAAAAAA")
    print(f"num_models = {num_models}")

    len_num_ens_mems = len(args.num_ens_mems)
    print(f"")
    print(f"AAAAAAAAAAAAAAAAAAAAAAAAAAA")
    print(f"len_num_ens_mems = {len_num_ens_mems}")
    if len_num_ens_mems != 1:
        if len_num_ens_mems != num_models:
            print(f"Bad!!")

    model_colors = [xml_colors[m] for m in args.colors]

    model_db_names = [model_names_in_database[m] for m in args.models]
    print(f"model_db_names = {model_db_names}")
    model_names_short_uc = [m.upper() for m in args.models]
    print(f"model_names_short_uc = {model_names_short_uc}")

    line_types = list()
    for imod in range(0,num_models):
        if incl_ens_means: line_types.append('b')
        line_types.extend(["l" for imem in range(0,args.num_ens_mems[imod])])

    line_widths = [1 for imod in range(0,num_models) for imem in range(0,args.num_ens_mems[imod])]

    num_series = sum(args.num_ens_mems[0:num_models])
    if incl_ens_means: num_series = num_series + num_models
    print(f"")
    print(f"XXXXXXXXXXXXXXXXXXXXXXXXXXXX")
    print(f"num_series = {num_series}")

    #order_series = [imod+(imem-1) for imod in range(1,num_models+1) for imem in range(1,args.num_ens_mems[imod-1]+1)]
    order_series = [s for s in range(1,num_series+1)]
    print(f"")
    print(f"BBBBBBBBBBBBBBBBBBBBBBBBBBBB")
    print(f"order_series = {order_series}")
    #lkjkj

    fcst_var_uc = args.fcst_var.upper()
    fcst_var_db_name = fcst_var_uc
    if fcst_var_uc == 'APCP': fcst_var_db_name = '_'.join([fcst_var_db_name, args.level_or_accum[0:2]])
    if args.stat in ['auc', 'brier', 'rely']: fcst_var_db_name = '_'.join([fcst_var_db_name, "ENS_FREQ"])
    if args.stat in ['auc', 'brier', 'rely', 'rhist']:
        fcst_var_db_name = '_'.join(filter(None,[fcst_var_db_name, ''.join([thresh_comp_oper, thresh_value])]))

    # Variable to contain a name for the verification statistic that MetViewer understands.
    stat_mv = args.stat.upper()
    if stat_mv == 'BIAS': stat_mv = 'ME'
    elif stat_mv == 'AUC': stat_mv = 'PSTD_ROC_AUC'
    elif stat_mv == 'BRIER': stat_mv = 'PSTD_BRIER'

    obs_type = ''
    if args.fcst_var == 'apcp' :
        obs_type = 'CCPA'
    elif args.fcst_var == 'refc' :
        obs_type = 'MRMS'
    elif var_lvl_str in ['DPT2m','TMP2m','WIND10m']:
        obs_type = 'ADPSFC'
    elif var_lvl_str in ['TMP850mb','WIND700mb']:
        obs_type = 'ADPUPA'

    logging.info(dedent(f"""
        Strings passed to jinja template:
          fcst_var_uc = {fcst_var_uc}
          fcst_var_db_name = {fcst_var_db_name}
          stat_mv = {stat_mv}
          obs_type = {obs_type}
        """))

    settings = {"database": args.database,
                "num_models": num_models,
                "model_colors": model_colors,
                "model_db_names": model_db_names,
                "model_names_short_uc": model_names_short_uc,
                "fcst_var_uc": fcst_var_uc,
                "fcst_var_db_name": fcst_var_db_name,
                "level_or_accum_mv": level_or_accum_mv,
                #"level_or_accum_no0pad": int(loa_value_no0pad),
                "level_or_accum_no0pad": loa_value_no0pad,
                "xml_threshold": xml_threshold,
                "obs_type": obs_type,
                "stat_uc": args.stat.upper(),
                "stat_lc": args.stat.lower(),
                "stat_mv": stat_mv,
                "line_types": line_types,
                "line_widths": line_widths,
                "num_series": num_series,
                "order_series": order_series,
                "num_ens_mems": args.num_ens_mems,
                "thresh_comp_oper": thresh_comp_oper,
                "thresh_value": thresh_value,
                "thresh_units": thresh_units,
                "num_fcsts": num_fcsts,
                "fcst_init_times": fcst_init_times,
                "fcst_len_hrs": args.fcst_len_hrs,
                "incl_ens_means": incl_ens_means,
                "job_title": job_title,
                "plot_title": plot_title}
    print(f"")
    print(f"BBBBBBBBBBBBBBBBBBBBBBBBBBB")
    print(f"settings = {settings}")

    template_fn = "".join(['./templates/', args.stat, '.xml'])
    if (args.stat in ['auc', 'brier']):
        template_fn = "".join(['./templates/auc_brier.xml'])
    elif (args.stat in ['bias', 'fbias']):
        template_fn = "".join(['./templates/bias_fbias.xml'])
    elif (args.stat in ['rely', 'rhist']):
        template_fn = "".join(['./templates/rely_rhist.xml'])

    logging.info(dedent(f"""
        Template file is:
          template_fn = {template_fn}
        """))

    #output_xml_path = ''.join(['./output_xmls/', args.stat])
    output_xml_path = os.path.join('./output_xmls', args.stat)
    print(f"output_xml_path = {output_xml_path}")
    #asdddddd
#print(os.path.join(path, "/home", "file.txt"))

    if not os.path.exists(output_xml_path):
        os.makedirs(output_xml_path)
    xml_fn = '_'.join(filter(None,[args.stat, ''.join([args.fcst_var.upper(), level_or_accum_str]),
                                   args.threshold, models_str]))
    xml_fn = ''.join(['./output_xmls/', args.stat, '/', xml_fn, '.xml'])
    logging.info(dedent(f"""
        Output xml file is:
          xml_fn = {xml_fn}
        """))

    yaml_settings = yaml.dump(settings)

    # Create MetViewer XML from Jinja template.
    args = ["-q", "-u", yaml_settings, '-t', template_fn, "-o", xml_fn]
    fill_jinja_template(args)

    # alsdkjf
    MV_BATCH="/d2/projects/METViewer/src/apps/METviewer/bin/mv_batch.sh"
    subprocess.run([MV_BATCH, xml_fn])

