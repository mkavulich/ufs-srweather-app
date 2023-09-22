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

import pprint
import subprocess

# Find the absolute paths to various directories.
from pathlib import Path
crnt_script_fp = Path(__file__).resolve()
# The index of file.parents will have to be changed if this script is moved to 
# elsewhere in the SRW directory structure.
ush_dir = crnt_script_fp.parents[2]
# The directory in which the SRW App is cloned.  This is one level up from ush_dir.
home_dir = Path(os.path.join(ush_dir, '..')).resolve()
# Get directory and name of current script.
#crnt_script_dir = str(crnt_script_fp.parent)
#crnt_script_fn = str(crnt_script_fp.name)

# Add ush_dir to the path so that python_utils can be imported.
sys.path.append(str(ush_dir))
from python_utils import (
    log_info,
    load_config_file,
)

# Add directories for accessing scripts/modules in the workflow-tools repo.
wt_src_dir = os.path.join(ush_dir, 'python_utils', 'workflow-tools', 'src')
sys.path.append(str(wt_src_dir))
wt_scripts_dir = os.path.join(ush_dir, 'python_utils', 'workflow-tools', 'scripts')
sys.path.append(str(wt_scripts_dir))
from templater import (
    set_template,
)

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
# wind        10m, 700mb        ge5mps (AUC,BRIER,RELY), ge10mps (AUC,BRIER,RELY)
#
def generate_metviewer_xml(argv):
    """Function that generates an xml file that MetViewer can read (in order
       to create a verification plot).

    Args:
        argv:  Command-line arguments

    Returns:
        None
    """

    # Set the logging level.
    logging.basicConfig(level=logging.INFO)

    # Parse arguments.
    parser = argparse.ArgumentParser(description=dedent(f'''
             Function to generate an xml file that MetViewer can read in order 
             to create a verification plot.
             '''))

    parser.add_argument('--mv_host',
                        type=str,
                        required=False, default='mohawk', 
                        help='Host (name of machine) on which MetViewer is installed')

    parser.add_argument('--mv_machine_config',
                        type=str,
                        required=False, default='config_mv_machine.yml', 
                        help='MetViewer machine (host) configuration file')

    parser.add_argument('--mv_database',
                        type=str,
                        required=False, default='mv_gefs_gdas_rtps_href_spring_2022', 
                        help='Name of MetViewer database on the machine')

    crnt_script_fp = Path(__file__).resolve()
    home_dir = crnt_script_fp.parents[3]
    expts_dir = Path(os.path.join(home_dir, '../expts_dir')).resolve()
    parser.add_argument('--mv_output_dir',
                        type=str,
                        required=False, default=os.path.join(expts_dir, 'mv_output2'),
                        help='Directory in which to place output (e.g. plots) from MetViewer')

    # Short and long names of verification statistics that may be plotted.
    stat_long_names = {'auc': 'Area Under the Curve',
                       'bias': 'Bias',
                       'brier': 'Brier Score',
                       'fbias': 'Frequency Bias',
                       'rely': 'Reliability',
                       'rhist': 'Rank Histogram',
                       'ss': 'Spread-Skill Ratio'}
    choices_stats = sorted(list(stat_long_names.keys()))

    # Short and long names of forecast variables on which verification may be run.
    fcst_var_long_names = {'apcp': 'Accumulated Precipitation',
                           'cape': 'Convenctive Available Potential Energy',
                           'dpt': 'Dew Point Temperature',
                           'hgt': 'Height',
                           'refc': 'Composite Reflectivity',
                           'tmp': 'Temperature',
                           'wind': 'Wind'}
    choices_fcst_vars = sorted(list(fcst_var_long_names.keys()))

    # Short names and names in MetViewer database of the models on which verification
    # can be run.  These have to be available (loaded) in the database.
    model_names_in_mv_database = {'gdas': 'RRFS_GDAS_GF.SPP.SPPT',
                                  'gefs': 'RRFS_GEFS_GF.SPP.SPPT',
                                  'href': 'HREF'}
    choices_models = sorted(list(model_names_in_mv_database.keys()))
    parser.add_argument('--model_names', nargs='+',
                        type=str.lower,
                        required=True,
                        choices=choices_models,
                        help='Names of models to include in xml and plots')

    parser.add_argument('--num_ens_mems', nargs='+',
                        type=int,
                        required=True,
                        help=dedent(f'''Number of ensemble members per model; if only one number
                                        is specified, all models are assumed to have the same
                                        number of members'''))

    # Set of allowed colors and the corresponding color codes that MetViewer recognizes.
    # NOTE:  These are incorrect, need to fix!!
    avail_metviewer_colors = {'red': '#ff0000FF',
                              'blue': '#8a2be2FF',
                              'green': '#32cd32FF'}
    choices_colors = list(avail_metviewer_colors.keys())
    parser.add_argument('--colors', nargs='+',
                        type=int,
                        required=False, default=choices_colors,
                        choices=choices_colors,
                        help='Color of each model used in line series, histogram, etc plots')

    parser.add_argument('--stat',
                        type=str.lower,
                        required=True,
                        choices=choices_stats,
                        help='Name of verification statistic/metric')

    parser.add_argument('--incl_ens_means',
                        required=False, action=argparse.BooleanOptionalAction, default=argparse.SUPPRESS,
                        help='Flag for including ensemble mean curves in plot')

    parser.add_argument('--fcst_init_info', nargs=3,
                        type=str,
                        required=True, 
                        help=dedent(f'''Initialization time of first forecast (in YYYYMMDDHH),
                                        number of forecasts, and forecast initialization interval (in HH)'''))

    parser.add_argument('--fcst_len_hrs',
                        type=int,
                        required=True,
                        help='Forecast length (in integer hours)')

    parser.add_argument('--fcst_var',
                        type=str.lower,
                        required=True, 
                        choices=choices_fcst_vars,
                        help='Name of forecast variable to verify')

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

    parser.add_argument('--level_or_accum',
                        type=str,
                        required=False,
                        choices=choices_level_or_accum,
                        help='Vertical level or accumulation period')

    valid_thresholds_by_fcst_var = {
        'apcp': ['gt0.0mm', 'ge2.54mm'],
        'cape': [''],
        'dpt': ['ge288K', 'ge293K'],
        'hgt': [''],
        'refc': ['ge20dBZ', 'ge30dBZ', 'ge40dBZ', 'ge50dBZ'],
        'tmp': ['ge288K', 'ge293K', 'ge298K', 'ge303K'],
        'wind': ['ge5mps', 'ge10mps'],
        }
    choices_thresholds = [item for sublist in valid_thresholds_by_fcst_var.values() for item in sublist]
    choices_thresholds = sorted(list(set(choices_thresholds)))

    parser.add_argument('--threshold',
                        type=str,
                        required=False, default='',
                        choices=choices_thresholds,
                        help='Threshold for specified forecast variable')

    args = parser.parse_args(argv)

    args_str = pprint.pformat(vars(args))
    args_str = '\n                 '.join(args_str.splitlines())
    logging.info(dedent(f"""
        List of arguments passed to this script:
          args = {args_str}
        """))

    mv_machine_config_fp = Path(os.path.join(args.mv_machine_config)).resolve()
    mv_machine_config = load_config_file(mv_machine_config_fp)

    mv_host = args.mv_host
    all_hosts = sorted(list(mv_machine_config.keys()))
    if args.mv_host not in all_hosts:
        logging.error(dedent(f"""
            The machine/host specified on the command line (mv_host) does not have a
            corresponding entry in the MetViewer host configuration file (mv_machine_config_fp):
              mv_host = {mv_host}
              mv_machine_config_fp = {mv_machine_config_fp}
            Machines that do have an entry in the host configuration file are:
              {all_hosts}
            Either run on one of these hosts, or add an entry in the configuration file for "{mv_host}".
            """))
        error_out

    mv_machine_config_dict = mv_machine_config[mv_host]
    print(f"")
    print(f"mv_machine_config_dict = {mv_machine_config_dict}")

    fcst_init_time_first = datetime.strptime(args.fcst_init_info[0], '%Y%m%d%H')
    num_fcsts = int(args.fcst_init_info[1])
    fcst_init_intvl = timedelta(hours=int(args.fcst_init_info[2]))
    fcst_init_times = list(range(0,num_fcsts))
    fcst_init_times = [fcst_init_time_first + i*fcst_init_intvl for i in fcst_init_times]
    fcst_init_times = [i.strftime("%Y-%m-%d %H:%M:%S") for i in fcst_init_times]

    fcst_init_times_str = '\n          '.join(fcst_init_times)
    logging.info(dedent(f"""
        Forecast initialization times (fcst_init_times):
          {fcst_init_times_str}
        """))

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
        error_out

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
            error_out

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
    var_lvl_str = ''.join(filter(None, [args.fcst_var.upper(), level_or_accum_str]))
    thresh_str = ''.join(filter(None, [thresh_comp_oper, thresh_value, thresh_units]))
    var_lvl_thresh_str = '_'.join(filter(None, [var_lvl_str, thresh_str]))

    models_str = '_'.join(args.model_names)
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

    num_models = len(args.model_names)
    len_num_ens_mems = len(args.num_ens_mems)
    if len_num_ens_mems == 1:
        args.num_ens_mems = [args.num_ens_mems[0] for n in range(num_models)]
        len_num_ens_mems = len(args.num_ens_mems)
    else:
        if len_num_ens_mems != num_models:
            logging.error(dedent(f"""
                Each model must have a number of ensemble members specified, or only 
                one number must be specified on the command line that represents the
                number of ensemble members for all specified models (i.e. num_models
                must equal len_num_ens_mems):
                  num_models = {num_models}
                  len_num_ens_mems = {len_num_ens_mems}
                """))
            error_out

    for i,model in enumerate(args.model_names):
        num_ens_mems = args.num_ens_mems[i]
        if num_ens_mems <= 0:
            logging.error(dedent(f"""
                The number of ensemble members for the current model must be greater
                than or equal to 0:
                  model = {model}
                  num_ens_mems = {num_ens_mems}
                """))
            error_out

    # Pick out the plot color associated with each model from the list of 
    # available colors.
    model_colors = [avail_metviewer_colors[m] for m in args.colors]

    model_db_names = [model_names_in_mv_database[m] for m in args.model_names]
    model_names_short_uc = [m.upper() for m in args.model_names]

    line_types = list()
    for imod in range(0,num_models):
        if incl_ens_means: line_types.append('b')
        line_types.extend(["l" for imem in range(0,args.num_ens_mems[imod])])

    line_widths = [1 for imod in range(0,num_models) for imem in range(0,args.num_ens_mems[imod])]

    num_series = sum(args.num_ens_mems[0:num_models])
    if incl_ens_means: num_series = num_series + num_models
    order_series = [s for s in range(1,num_series+1)]

    # Generate name of forecast variable as it appears in the MetViewer database.
    fcst_var_uc = args.fcst_var.upper()
    fcst_var_db_name = fcst_var_uc
    if fcst_var_uc == 'APCP': fcst_var_db_name = '_'.join([fcst_var_db_name, args.level_or_accum[0:2]])
    if args.stat in ['auc', 'brier', 'rely']: fcst_var_db_name = '_'.join([fcst_var_db_name, "ENS_FREQ"])
    if args.stat in ['auc', 'brier', 'rely', 'rhist']:
        fcst_var_db_name = '_'.join(filter(None,[fcst_var_db_name, ''.join([thresh_comp_oper, thresh_value])]))

    # Generate name for the verification statistic that MetViewer understands.
    stat_mv = args.stat.upper()
    if stat_mv == 'BIAS': stat_mv = 'ME'
    elif stat_mv == 'AUC': stat_mv = 'PSTD_ROC_AUC'
    elif stat_mv == 'BRIER': stat_mv = 'PSTD_BRIER'

    # For the given forecast variable, generate a name for the corresponding
    # observation type in the MetViewer database.
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

    # Create dictionary containing values for the variables appearing in the
    # jinja template.
    jinja_vars = {"mv_host": args.mv_host,
                  "mv_machine_config_dict": mv_machine_config_dict,
                  "mv_database": args.mv_database,
                  "mv_output_dir": args.mv_output_dir,
                  "num_models": num_models,
                  "model_colors": model_colors,
                  "model_db_names": model_db_names,
                  "model_names_short_uc": model_names_short_uc,
                  "fcst_var_uc": fcst_var_uc,
                  "fcst_var_db_name": fcst_var_db_name,
                  "level_or_accum_mv": level_or_accum_mv,
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

    jinja_vars_str = pprint.pformat(jinja_vars, compact=True)
    jinja_vars_str = '\n          '.join(jinja_vars_str.splitlines())
    logging.info(dedent(f"""
        Jinja variables (jinja_vars) passed to template:
          {jinja_vars_str}
        """))

    templates_dir = os.path.join(home_dir, 'parm', 'metviewer')
    template_fn = "".join([args.stat, '.xml'])
    if (args.stat in ['auc', 'brier']):
        template_fn = 'auc_brier.xml'
    elif (args.stat in ['bias', 'fbias']):
        template_fn = 'bias_fbias.xml'
    elif (args.stat in ['rely', 'rhist']):
        template_fn = 'rely_rhist.xml'
    template_fp = os.path.join(templates_dir, template_fn)

    logging.info(dedent(f"""
        Template file is:
          templates_dir = {templates_dir}
          template_fn = {template_fn}
          template_fp = {template_fp}
        """))

    # Place xmls generated below in the same directory as the plots that 
    # MetViewer will generate from the xmls.
    output_xml_dir = Path(os.path.join(args.mv_output_dir, 'plots')).resolve()
    if not os.path.exists(output_xml_dir):
        os.makedirs(output_xml_dir)
    output_xml_fn = '_'.join(filter(None,[args.stat, ''.join([args.fcst_var.upper(), level_or_accum_str]),
                                          args.threshold, models_str]))
    output_xml_fn = ''.join([output_xml_fn, '.xml'])
    output_xml_fp = os.path.join(output_xml_dir, output_xml_fn)
    logging.info(dedent(f"""
        Output xml file information:
          output_xml_fn = {output_xml_fn}
          output_xml_dir = {output_xml_dir}
          output_xml_fp = {output_xml_fp}
        """))

    # Convert the dictionary of jinja variable settings above to yaml format
    # and write it to a temporary yaml file for reading by the set_template
    # function.
    tmp_fn = 'tmp.yaml'
    with open(f'{tmp_fn}', 'w') as fn:
        yaml_vars = yaml.dump(jinja_vars, fn)

    args = ['--quiet', '--config_file', tmp_fn, '--input_template', template_fp, "--outfile", output_xml_fp]
    set_template(args)
    os.remove(tmp_fn)

    return(mv_machine_config_dict["mv_batch"], output_xml_fp)


def run_mv_batch(mv_batch, output_xml_fp):
    """Function that generates a verification plot using MetViewer.

    Args:
        mv_batch:       Path to MetViewer batch plotting script.
        output_xml_fp:  Full path to the xml to pass to the batch script.

    Returns:
        None
    """

    # Run MetViewer in batch mode on the xml.
    subprocess.run([mv_batch, output_xml_fp])


def plot_vx_metviewer(args):

    # Pass command line arguments (except for very first one) to the function
    # that generates a MetViewer xml.
    mv_batch, output_xml_fp = generate_metviewer_xml(args)
    # Run MetViewer on the xml.
    run_mv_batch(mv_batch, output_xml_fp)
#
# -----------------------------------------------------------------------
#
# Call the function defined above.
#
# -----------------------------------------------------------------------
#
if __name__ == "__main__":
    plot_vx_metviewer(sys.argv[1:])

