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

def get_static_vals(static_fp):
    '''
    Function to read in values that are mostly static, i.e. they're usually
    not expected to change from one call to this script to another (e.g.
    valid values for various parameters).
    '''

    # Load the yaml file containing static values.
    valid_vals = load_config_file(static_fp)

    # Define local dictionaries containing static values that depend on the 
    # forecast variable.
    valid_fcst_vars = valid_vals['fcst_vars'].keys()
    fcst_var_long_names = {}
    valid_levels_or_accums_by_fcst_var = {}
    valid_thresholds_by_fcst_var = {}
    for fcst_var in valid_fcst_vars:
        fcst_var_long_names[fcst_var] = valid_vals['fcst_vars'][fcst_var]['long_name']
        valid_levels_or_accums_by_fcst_var[fcst_var] = valid_vals['fcst_vars'][fcst_var]['valid_levels']
        valid_thresholds_by_fcst_var[fcst_var] = valid_vals['fcst_vars'][fcst_var]['valid_thresholds']

    # Define local dictionaries containing static values that depend on the 
    # verification statistic.
    valid_stats = valid_vals['stats'].keys()
    stat_long_names = {}
    stat_need_thresh = {}
    for stat in valid_stats:
        stat_long_names[stat] = valid_vals['stats'][stat]['long_name']
        stat_need_thresh[stat] = valid_vals['stats'][stat]['need_thresh']

    # Get dictionary containing MetViewer color codes.  Keys are the color
    # names (e.g. 'red'), and values are the corresponding codes in MetViewer.
    mv_color_codes = valid_vals['mv_color_codes']

    # Create dictionary containing valid choices for various parameters.
    # This is needed by the argument parsing function below.
    choices = {}

    choices['fcst_var'] = sorted(valid_fcst_vars)

    choices['level'] = [item for sublist in valid_levels_or_accums_by_fcst_var.values() for item in sublist]
    # The above list of level (or accumulation) choices may contain duplicate values and is unsorted.
    # Remove duplicates and sort.
    choices['level'] = sorted(list(set(choices['level'])))

    choices['threshold'] = [item for sublist in valid_thresholds_by_fcst_var.values() for item in sublist]
    # The above list of threshold choices may contain duplicate values and is unsorted.
    # Remove duplicates and sort.
    choices['threshold'] = sorted(list(set(choices['threshold'])))

    choices['stat'] = sorted(valid_stats)

    choices['color'] = list(mv_color_codes.keys())

    static = {}
    static['fcst_var_long_names'] = fcst_var_long_names
    static['valid_levels_or_accums_by_fcst_var'] = valid_levels_or_accums_by_fcst_var
    static['valid_thresholds_by_fcst_var'] = valid_thresholds_by_fcst_var
    static['stat_long_names'] = stat_long_names
    static['stat_need_thresh'] = stat_need_thresh
    static['mv_color_codes'] = mv_color_codes 
    static['choices'] = choices

    return static


def get_database_info(mv_database_config_fp):
    '''
    Function to read in information about the MetViewer database from which
    verification statistics will be plotted.
    '''

    # Load the yaml file containing database information.
    mv_database_info = load_config_file(mv_database_config_fp)

    return mv_database_info


def parse_args(argv, static, mv_database_info):
    '''
    Function to parse arguments for this script.
    '''

    fcst_var_long_names = static['fcst_var_long_names']
    valid_levels_or_accums_by_fcst_var = static['valid_levels_or_accums_by_fcst_var']
    valid_thresholds_by_fcst_var = static['valid_thresholds_by_fcst_var']
    stat_long_names = static['stat_long_names']
    stat_need_thresh = static['stat_need_thresh']
    mv_color_codes = static['mv_color_codes']
    choices = static['choices']

    # For uniformity, add the allowed values for the model names to the "choices"
    # dictionary.
    choices['model'] = mv_database_info['models'].keys()

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
                        required=False, default='mv_machine_config.yml', 
                        help='MetViewer machine (host) configuration file')

    parser.add_argument('--mv_database_config',
                        type=str,
                        required=False, default='mv_database_config.yml',
                        help='MetViewer database configuration file')

    crnt_script_fp = Path(__file__).resolve()
    home_dir = crnt_script_fp.parents[3]
    expts_dir = Path(os.path.join(home_dir, '../expts_dir')).resolve()
    parser.add_argument('--mv_output_dir',
                        type=str,
                        required=False, default=os.path.join(expts_dir, 'mv_output'),
                        help='Directory in which to place output (e.g. plots) from MetViewer')

    parser.add_argument('--model_names', nargs='+',
                        type=str.lower,
                        required=True,
                        choices=choices['model'],
                        help='Names of models to include in xml and plots')

    parser.add_argument('--colors', nargs='+',
                        type=int,
                        required=False, default=choices['color'],
                        #choices=choices_colors,
                        choices=choices['color'],
                        help='Color of each model used in line series, histogram, etc plots')

    parser.add_argument('--stat',
                        type=str.lower,
                        required=True,
                        #choices=choices_stats,
                        choices=choices['stat'],
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
                        #choices=choices_fcst_vars,
                        choices=choices['fcst_var'],
                        help='Name of forecast variable to verify')

    parser.add_argument('--level_or_accum',
                        type=str,
                        required=False,
                        #choices=choices_level_or_accum,
                        choices=choices['level'],
                        help='Vertical level or accumulation period')

    parser.add_argument('--threshold',
                        type=str,
                        required=False, default='',
                        #choices=choices_thresholds,
                        choices=choices['threshold'],
                        help='Threshold for specified forecast variable')

    cla = parser.parse_args(argv)

    cla_str = pprint.pformat(vars(cla))
    cla_str = '\n                 '.join(cla_str.splitlines())
    logging.info(dedent(f"""
        List of arguments passed to this script:
          cla = {cla_str}
        """))

    return cla


def generate_metviewer_xml(cla, static, mv_database_info):
    """Function that generates an xml file that MetViewer can read (in order
       to create a verification plot).

    Args:
        argv:  Command-line arguments

    Returns:
        None
    """

    fcst_var_long_names = static['fcst_var_long_names']
    valid_levels_or_accums_by_fcst_var = static['valid_levels_or_accums_by_fcst_var']
    valid_thresholds_by_fcst_var = static['valid_thresholds_by_fcst_var']
    stat_long_names = static['stat_long_names']
    stat_need_thresh = static['stat_need_thresh']
    mv_color_codes = static['mv_color_codes']

    # Set the logging level.
    logging.basicConfig(level=logging.INFO)

    # Load the machine configuration file into a dictionary and find in it the
    # machine specified on the command line.
    mv_machine_config_fp = Path(os.path.join(cla.mv_machine_config)).resolve()
    mv_machine_config = load_config_file(mv_machine_config_fp)

    mv_host = cla.mv_host
    all_hosts = sorted(list(mv_machine_config.keys()))
    if cla.mv_host not in all_hosts:
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

    fcst_init_time_first = datetime.strptime(cla.fcst_init_info[0], '%Y%m%d%H')
    num_fcsts = int(cla.fcst_init_info[1])
    fcst_init_intvl = timedelta(hours=int(cla.fcst_init_info[2]))
    fcst_init_times = list(range(0,num_fcsts))
    fcst_init_times = [fcst_init_time_first + i*fcst_init_intvl for i in fcst_init_times]
    fcst_init_times = [i.strftime("%Y-%m-%d %H:%M:%S") for i in fcst_init_times]

    fcst_init_times_str = '\n          '.join(fcst_init_times)
    logging.info(dedent(f"""
        Forecast initialization times (fcst_init_times):
          {fcst_init_times_str}
        """))

    if ('incl_ens_means' not in cla):
        incl_ens_means = False
        if (cla.stat == 'bias'): incl_ens_means = True
    else:
        incl_ens_means = cla.incl_ens_means
    # Apparently we can just reset or create incl_ens_means within the cla Namespace
    # as follows:
    cla.incl_ens_means = incl_ens_means

    valid_levels_or_accums = valid_levels_or_accums_by_fcst_var[cla.fcst_var]
    if cla.level_or_accum not in valid_levels_or_accums:
        logging.error(dedent(f"""
            The specified level or accumulation is not compatible with the specified forecast variable:
              fcst_var = {cla.fcst_var}
              level_or_accum = {cla.level_or_accum}
            Valid options for level or accumulation for this forecast variable are:
              {valid_levels_or_accums}
            """))
        error_out

    loa = re.findall(r'(\d*\.*\d+)([A-Za-z]+)', cla.level_or_accum)
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
    level_or_accum_mv = cla.level_or_accum
    if loa_units == 'm':
        level_or_accum_mv = ''.join(['Z', loa_value_no0pad])
    elif loa_units == 'mb':
        level_or_accum_mv = ''.join(['P', loa_value_no0pad])
    elif loa_units in ['h', 'hr']:
        level_or_accum_mv = ''.join(['A', loa_value_no0pad])

    if (not stat_need_thresh[cla.stat]) and (cla.threshold):
        no_thresh_stats_fmt_str = ",\n".join("              {!r}: {!r}".format(k, v) for k, v in stat_long_names.items() if k in no_thresh_stats).lstrip()
        logging.info(dedent(f"""
            A threshold is not needed when working with one of the following verification stats:
              {no_thresh_stats_fmt_str}
            Thus, the threshold specified in the argument list ("{cla.threshold}") will be reset to an empty string.
            """))
        cla.threshold = ''

    elif (stat_need_thresh[cla.stat]):
        valid_thresholds = valid_thresholds_by_fcst_var[cla.fcst_var]
        if cla.threshold not in valid_thresholds:
            logging.error(dedent(f"""
                The specified threshold is not compatible with the specified forecast variable:
                  fcst_var = {cla.fcst_var}
                  threshold = {cla.threshold}
                Valid options for threshold for this forecast variable are:
                  {valid_thresholds}
                """))
            # Need proper exit here!
            error_out

    threshold = re.findall(r'([A-Za-z]+)(\d*\.*\d+)([A-Za-z]+)', cla.threshold)
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

    level_or_accum_str = cla.level_or_accum
    if level_or_accum_str == 'L0': level_or_accum_str = ''
    plot_title = " ".join(filter(None,
                          [stat_long_names[cla.stat], 'for',
                           level_or_accum_str, fcst_var_long_names[cla.fcst_var],
                           xml_threshold, thresh_units]))
    var_lvl_str = ''.join(filter(None, [cla.fcst_var.upper(), level_or_accum_str]))
    thresh_str = ''.join(filter(None, [thresh_comp_oper, thresh_value, thresh_units]))
    var_lvl_thresh_str = '_'.join(filter(None, [var_lvl_str, thresh_str]))

    models_str = '_'.join(cla.model_names)
    job_title = '_'.join([cla.stat, var_lvl_thresh_str, models_str])

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

    model_info = mv_database_info['models']
    num_models = len(model_info)
    num_ens_mems = [model_info[m]['num_ens_mems'] for m in cla.model_names]
    for i,model in enumerate(cla.model_names):
        n_ens = num_ens_mems[i]
        if n_ens <= 0:
            logging.error(dedent(f"""
                The number of ensemble members for the current model must be greater
                than or equal to 0:
                  model = {model}
                  n_ens = {n_ens}
                """))
            error_out

    # Pick out the plot color associated with each model from the list of 
    # available colors.
    model_color_codes = [mv_color_codes[m] for m in cla.colors]

    model_db_names = [model_info[m]['name_in_db'] for m in cla.model_names]
    model_names_short_uc = [m.upper() for m in cla.model_names]

    line_types = list()
    for imod in range(0,num_models):
        if incl_ens_means: line_types.append('b')
        line_types.extend(["l" for imem in range(0,num_ens_mems[imod])])

    line_widths = [1 for imod in range(0,num_models) for imem in range(0,num_ens_mems[imod])]

    num_series = sum(num_ens_mems[0:num_models])
    if incl_ens_means: num_series = num_series + num_models
    order_series = [s for s in range(1,num_series+1)]

    # Generate name of forecast variable as it appears in the MetViewer database.
    fcst_var_uc = cla.fcst_var.upper()
    fcst_var_db_name = fcst_var_uc
    if fcst_var_uc == 'APCP': fcst_var_db_name = '_'.join([fcst_var_db_name, cla.level_or_accum[0:2]])
    if cla.stat in ['auc', 'brier', 'rely']: fcst_var_db_name = '_'.join([fcst_var_db_name, "ENS_FREQ"])
    if cla.stat in ['auc', 'brier', 'rely', 'rhist']:
        fcst_var_db_name = '_'.join(filter(None,[fcst_var_db_name, ''.join([thresh_comp_oper, thresh_value])]))

    # Generate name for the verification statistic that MetViewer understands.
    stat_mv = cla.stat.upper()
    if stat_mv == 'BIAS': stat_mv = 'ME'
    elif stat_mv == 'AUC': stat_mv = 'PSTD_ROC_AUC'
    elif stat_mv == 'BRIER': stat_mv = 'PSTD_BRIER'

    # For the given forecast variable, generate a name for the corresponding
    # observation type in the MetViewer database.
    obs_type = ''
    if cla.fcst_var == 'apcp' :
        obs_type = 'CCPA'
    elif cla.fcst_var == 'refc' :
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
    jinja_vars = {"mv_host": cla.mv_host,
                  "mv_machine_config_dict": mv_machine_config_dict,
                  "mv_database": mv_database_info['db_name'],
                  "mv_output_dir": cla.mv_output_dir,
                  "num_models": num_models,
                  "model_color_codes": model_color_codes,
                  "model_db_names": model_db_names,
                  "model_names_short_uc": model_names_short_uc,
                  "fcst_var_uc": fcst_var_uc,
                  "fcst_var_db_name": fcst_var_db_name,
                  "level_or_accum_mv": level_or_accum_mv,
                  "level_or_accum_no0pad": loa_value_no0pad,
                  "xml_threshold": xml_threshold,
                  "obs_type": obs_type,
                  "stat_uc": cla.stat.upper(),
                  "stat_lc": cla.stat.lower(),
                  "stat_mv": stat_mv,
                  "line_types": line_types,
                  "line_widths": line_widths,
                  "num_series": num_series,
                  "order_series": order_series,
                  "num_ens_mems": num_ens_mems,
                  "thresh_comp_oper": thresh_comp_oper,
                  "thresh_value": thresh_value,
                  "thresh_units": thresh_units,
                  "num_fcsts": num_fcsts,
                  "fcst_init_times": fcst_init_times,
                  "fcst_len_hrs": cla.fcst_len_hrs,
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
    template_fn = "".join([cla.stat, '.xml'])
    if (cla.stat in ['auc', 'brier']):
        template_fn = 'auc_brier.xml'
    elif (cla.stat in ['bias', 'fbias']):
        template_fn = 'bias_fbias.xml'
    elif (cla.stat in ['rely', 'rhist']):
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
    output_xml_dir = Path(os.path.join(cla.mv_output_dir, 'plots')).resolve()
    if not os.path.exists(output_xml_dir):
        os.makedirs(output_xml_dir)
    output_xml_fn = '_'.join(filter(None,
                    ['plot', cla.stat,
                     ''.join([cla.fcst_var.upper(), level_or_accum_str]),
                     cla.threshold, models_str]))
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

    args_list = ['--quiet',
                 '--config_file', tmp_fn,
                 '--input_template', template_fp,
                 '--outfile', output_xml_fp]
    set_template(args_list)
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


def plot_vx_metviewer(argv):

    # Get static parameters.  These include parameters (e.g. valid values) 
    # needed to parse the command line arguments.
    static_fp = 'vx_plots_static.yml'
    static = get_static_vals(static_fp)

    # Get MetViewer database information.
    mv_database_config_fp = 'mv_database_config.yml'
    mv_database_info = get_database_info(mv_database_config_fp)

    # Parse arguments.
    cla = parse_args(argv, static, mv_database_info)

    # Generates a MetViewer xml.
    mv_batch, output_xml_fp = generate_metviewer_xml(cla, static, mv_database_info)

    # Run MetViewer on the xml to create a verification plot.
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

