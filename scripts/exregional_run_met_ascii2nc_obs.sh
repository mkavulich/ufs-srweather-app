#!/usr/bin/env bash

#
#-----------------------------------------------------------------------
#
# Source the variable definitions file and the bash utility functions.
#
#-----------------------------------------------------------------------
#
. $USHdir/source_util_funcs.sh
source_config_for_task "task_run_met_ascii2nc_obs" ${GLOBAL_VAR_DEFNS_FP}
#
#-----------------------------------------------------------------------
#
# Source files defining auxiliary functions for verification.
#
#-----------------------------------------------------------------------
#
. $USHdir/get_metplus_tool_name.sh
. $USHdir/set_vx_params.sh
. $USHdir/set_vx_fhr_list.sh
#
#-----------------------------------------------------------------------
#
# Save current shell options (in a global array).  Then set new options
# for this script/function.
#
#-----------------------------------------------------------------------
#
{ save_shell_opts; . $USHdir/preamble.sh; } > /dev/null 2>&1
#
#-----------------------------------------------------------------------
#
# Get the full path to the file in which this script/function is located
# (scrfunc_fp), the name of that file (scrfunc_fn), and the directory in
# which the file is located (scrfunc_dir).
#
#-----------------------------------------------------------------------
#
scrfunc_fp=$( $READLINK -f "${BASH_SOURCE[0]}" )
scrfunc_fn=$( basename "${scrfunc_fp}" )
scrfunc_dir=$( dirname "${scrfunc_fp}" )
#
#-----------------------------------------------------------------------
#
# Get the name of the MET/METplus tool in different formats that may be
# needed from the global variable METPLUSTOOLNAME.
#
#-----------------------------------------------------------------------
#
set -x
get_metplus_tool_name \
  METPLUSTOOLNAME="${METPLUSTOOLNAME}" \
  outvarname_metplus_tool_name="metplus_tool_name" \
  outvarname_MetplusToolName="MetplusToolName" \
  outvarname_METPLUS_TOOL_NAME="METPLUS_TOOL_NAME"
#
#-----------------------------------------------------------------------
#
print_info_msg "
========================================================================
Entering script:  \"${scrfunc_fn}\"
In directory:     \"${scrfunc_dir}\"

This is the ex-script for the task that runs the METplus tool ${MetplusToolName}
to convert ASCII format observation files to NetCDF format.
========================================================================"
#
CDATE="${PDY}${cyc}"
#
#-----------------------------------------------------------------------
#
# Set various verification parameters associated with the field to be
# verified.  Not all of these are necessarily used later below but are
# set here for consistency with other verification ex-scripts.
#
#-----------------------------------------------------------------------
#
FIELDNAME_IN_OBS_INPUT=""
FIELDNAME_IN_FCST_INPUT=""
FIELDNAME_IN_MET_OUTPUT=""
FIELDNAME_IN_MET_FILEDIR_NAMES=""

set_vx_params \
  obtype="${OBTYPE}" \
  field="$VAR" \
  accum_hh="${ACCUM_HH}" \
  outvarname_grid_or_point="grid_or_point" \
  outvarname_fieldname_in_obs_input="FIELDNAME_IN_OBS_INPUT" \
  outvarname_fieldname_in_fcst_input="FIELDNAME_IN_FCST_INPUT" \
  outvarname_fieldname_in_MET_output="FIELDNAME_IN_MET_OUTPUT" \
  outvarname_fieldname_in_MET_filedir_names="FIELDNAME_IN_MET_FILEDIR_NAMES"
#
#-----------------------------------------------------------------------
#
# Set paths and file templates for input to and output from the MET/
# METplus tool to be run as well as other file/directory parameters.
#
#-----------------------------------------------------------------------
#
vx_output_basedir=$( eval echo "${VX_OUTPUT_BASEDIR}" )

OBS_INPUT_DIR="${OBS_DIR}"

OUTPUT_BASE="${vx_output_basedir}"
OUTPUT_DIR="${OUTPUT_BASE}/metprd/${MetplusToolName}_obs"
STAGING_DIR="${OUTPUT_BASE}/stage/${MetplusToolName}_obs"
if [ "${OBTYPE}" = "AERONET" ]; then
  OBS_INPUT_FN_TEMPLATE=${OBS_AERONET_FN_TEMPLATE}
  OUTPUT_FN_TEMPLATE=${OBS_AERONET_FN_TEMPLATE_ASCII2NC_OUTPUT}
  ASCII2NC_INPUT_FORMAT=aeronetv3
elif [ "${OBTYPE}" = "AIRNOW" ]; then
  OBS_INPUT_FN_TEMPLATE=${OBS_AIRNOW_FN_TEMPLATE}
  OUTPUT_FN_TEMPLATE=${OBS_AIRNOW_FN_TEMPLATE_ASCII2NC_OUTPUT}
  ASCII2NC_INPUT_FORMAT=airnowhourlyaqobs
else
  print_err_msg_exit "\nNo filename template set for OBTYPE \"${OBTYPE}\"!"
fi
#-----------------------------------------------------------------------
#
# Set the array of forecast hours for which to run the MET/METplus tool.
#
#-----------------------------------------------------------------------
#
set_vx_fhr_list \
  cdate="${CDATE}" \
  fcst_len_hrs="${FCST_LEN_HRS}" \
  field="$VAR" \
  accum_hh="${ACCUM_HH}" \
  base_dir="${OBS_INPUT_DIR}" \
  fn_template="${OBS_INPUT_FN_TEMPLATE}" \
  check_accum_contrib_files="FALSE" \
  num_missing_files_max="${NUM_MISSING_OBS_FILES_MAX}" \
  outvarname_fhr_list="FHR_LIST"
#
#-----------------------------------------------------------------------
#
# Make sure the MET/METplus output directory(ies) exists.
#
#-----------------------------------------------------------------------
#
mkdir -p "${OUTPUT_DIR}"
#
#-----------------------------------------------------------------------
#
# Check for existence of top-level OBS_DIR.
#
#-----------------------------------------------------------------------
#
if [ ! -d "${OBS_DIR}" ]; then
  print_err_msg_exit "\
OBS_DIR does not exist or is not a directory:
  OBS_DIR = \"${OBS_DIR}\""
fi
#
#-----------------------------------------------------------------------
#
# Export variables needed in the common METplus configuration file (at
# ${METPLUS_CONF}/common.conf).
#
#-----------------------------------------------------------------------
#
export METPLUS_CONF
export LOGDIR
#
#-----------------------------------------------------------------------
#
# Do not run METplus if there isn't at least one valid forecast hour for
# which to run it.
#
#-----------------------------------------------------------------------
#
if [ -z "${FHR_LIST}" ]; then
  print_err_msg_exit "\
The list of forecast hours for which to run METplus is empty:
  FHR_LIST = [${FHR_LIST}]"
fi
#
#-----------------------------------------------------------------------
#
# Set the names of the template METplus configuration file, the METplus
# configuration file generated from this template, and the METplus log
# file.
#
#-----------------------------------------------------------------------
#
# First, set the base file names.
#
metplus_config_tmpl_fn="${MetplusToolName}_obs"
#
# Note that we append the cycle date to the name of the configuration
# file because we are considering only observations when using ASCII2NC, so
# the output files from METplus are not placed under cycle directories.
# Thus, another method is necessary to associate the configuration file
# with the cycle for which it is used.
#
# Note also that if considering an ensemble forecast, we include the
# ensemble member name to the config file name.  This is necessary in
# NCO mode (i.e. when RUN_ENVIR = "nco") because in that mode, the
# directory tree under which the configuration file is placed does not
# contain member information, so the file names must include it.  It is
# not necessary in community mode (i.e. when RUN_ENVIR = "community")
# because in that case, the directory structure does contain the member
# information, but we still include that info in the file name so that
# the behavior in the two modes is as similar as possible.
#
metplus_config_fn="${metplus_config_tmpl_fn}_${CDATE}"
metplus_log_fn="${metplus_config_fn}"
#
# Add prefixes and suffixes (extensions) to the base file names.
#
metplus_config_tmpl_fn="${metplus_config_tmpl_fn}.conf"
metplus_config_fn="${metplus_config_fn}.conf"
metplus_log_fn="metplus.log.${metplus_log_fn}"
#
#-----------------------------------------------------------------------
#
# Generate the METplus configuration file from its jinja template.
#
#-----------------------------------------------------------------------
#
# Set the full paths to the jinja template METplus configuration file
# (which already exists) and the METplus configuration file that will be
# generated from it.
#
metplus_config_tmpl_fp="${METPLUS_CONF}/${metplus_config_tmpl_fn}"
metplus_config_fp="${OUTPUT_DIR}/${metplus_config_fn}"
#
# Define variables that appear in the jinja template.
#
settings="\
#
# MET/METplus information.
#
  'metplus_tool_name': '${metplus_tool_name}'
  'MetplusToolName': '${MetplusToolName}'
  'METPLUS_TOOL_NAME': '${METPLUS_TOOL_NAME}'
  'metplus_verbosity_level': '${METPLUS_VERBOSITY_LEVEL}'
#
# Date and forecast hour information.
#
  'cdate': '$CDATE'
  'fhr_list': '${FHR_LIST}'
#
# Input and output directory/file information.
#
  'metplus_config_fn': '${metplus_config_fn:-}'
  'metplus_log_fn': '${metplus_log_fn:-}'
  'obs_input_dir': '${OBS_INPUT_DIR:-}'
  'obs_input_fn_template': '${OBS_INPUT_FN_TEMPLATE:-}'
  'fcst_input_dir': '${FCST_INPUT_DIR:-}'
  'fcst_input_fn_template': '${FCST_INPUT_FN_TEMPLATE:-}'
  'output_base': '${OUTPUT_BASE}'
  'output_dir': '${OUTPUT_DIR}'
  'output_fn_template': '${OUTPUT_FN_TEMPLATE:-}'
  'staging_dir': '${STAGING_DIR}'
  'vx_fcst_model_name': '${VX_FCST_MODEL_NAME}'
  'input_format': '${ASCII2NC_INPUT_FORMAT}'
#
# Ensemble and member-specific information.
#
  'num_ens_members': '${NUM_ENS_MEMBERS}'
  'ensmem_name': '${ensmem_name:-}'
  'time_lag': '${time_lag:-}'
#
# Field information.
#
  'fieldname_in_obs_input': '${FIELDNAME_IN_OBS_INPUT}'
  'fieldname_in_fcst_input': '${FIELDNAME_IN_FCST_INPUT}'
  'fieldname_in_met_output': '${FIELDNAME_IN_MET_OUTPUT}'
  'fieldname_in_met_filedir_names': '${FIELDNAME_IN_MET_FILEDIR_NAMES}'
  'obtype': '${OBTYPE}'
  'accum_hh': '${ACCUM_HH:-}'
  'accum_no_pad': '${ACCUM_NO_PAD:-}'
"

# Render the template to create a METplus configuration file
tmpfile=$( $READLINK -f "$(mktemp ./met_plus_settings.XXXXXX.yaml)")
printf "%s" "$settings" > "$tmpfile"
uw template render \
  -i ${metplus_config_tmpl_fp} \
  -o ${metplus_config_fp} \
  --verbose \
  --values-file "${tmpfile}" \
  --search-path "/" 

err=$?
rm $tmpfile
if [ $err -ne 0 ]; then
  message_txt="Error rendering template for METplus config.
     Contents of input are:
$settings"
  if [ "${RUN_ENVIR}" = "nco" ] && [ "${MACHINE}" = "WCOSS2" ]; then
    err_exit "${message_txt}"
  else
    print_err_msg_exit "${message_txt}"
  fi
fi
#
#-----------------------------------------------------------------------
#
# Call METplus.
#
#-----------------------------------------------------------------------
#
#TEMPORARILY POINTING TO BETA RELEASE
MET_ROOT=/contrib/met/12.0.0-beta3
MET_INSTALL_DIR=${MET_ROOT}
MET_BIN_EXEC=${MET_INSTALL_DIR}/bin
MET_BASE=${MET_INSTALL_DIR}/share/met
METPLUS_ROOT=/contrib/METplus/METplus-6.0.0-beta3/
METPLUS_PATH=${METPLUS_ROOT}
MET_ROOT=/contrib/met/12.0.0-beta3
#TEMPORARILY POINTING TO BETA RELEASE
print_info_msg "$VERBOSE" "
Calling METplus to run MET's ${metplus_tool_name} tool on observations of type: ${OBTYPE}"
${METPLUS_PATH}/ush/run_metplus.py \
  -c ${METPLUS_CONF}/common.conf \
  -c ${metplus_config_fp} || \
print_err_msg_exit "
Call to METplus failed with return code: $?
METplus configuration file used is:
  metplus_config_fp = \"${metplus_config_fp}\""
#
#-----------------------------------------------------------------------
#
# Print message indicating successful completion of script.
#
#-----------------------------------------------------------------------
#
print_info_msg "
========================================================================
METplus ${MetplusToolName} tool completed successfully.

Exiting script:  \"${scrfunc_fn}\"
In directory:    \"${scrfunc_dir}\"
========================================================================"
#
#-----------------------------------------------------------------------
#
# Restore the shell options saved at the beginning of this script/func-
# tion.
#
#-----------------------------------------------------------------------
#
{ restore_shell_opts; } > /dev/null 2>&1
