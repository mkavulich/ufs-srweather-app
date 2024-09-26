#!/usr/bin/env bash

#
#-----------------------------------------------------------------------
#
# The ex-script for checking the post output.
#
# Run-time environment variables:
#
#    ACCUM_HH
#    CDATE
#    ENSMEM_INDX
#    GLOBAL_VAR_DEFNS_FP
#    METPLUS_ROOT (used by ush/set_vx_fhr_list.py)
#    VAR
#
# Experiment variables
#
#  user:
#    USHdir
#
#  workflow:
#    FCST_LEN_HRS
#
#  global:
#    DO_ENSEMBLE
#    ENS_TIME_LAG_HRS
#
#  verification:
#    FCST_FN_TEMPLATE
#    FCST_SUBDIR_TEMPLATE
#    NUM_MISSING_FCST_FILES_MAX
#    VX_FCST_INPUT_BASEDIR
#    VX_NDIGITS_ENSMEM_NAMES
#
#  constants:
#    SECS_PER_HOUR
#
#-----------------------------------------------------------------------
#

#
#-----------------------------------------------------------------------
#
# Source the variable definitions file and the bash utility functions.
#
#-----------------------------------------------------------------------
#
. $USHdir/source_util_funcs.sh
for sect in user nco workflow global verification constants task_run_post ; do
  source_yaml ${GLOBAL_VAR_DEFNS_FP} ${sect}
done
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
# Print message indicating entry into script.
#
#-----------------------------------------------------------------------
#
print_info_msg "
========================================================================
Entering script:  \"${scrfunc_fn}\"
In directory:     \"${scrfunc_dir}\"

This is the ex-script for the task that checks that no more than
NUM_MISSING_FCST_FILES_MAX of each forecast's (ensemble member's) post-
processed output files are missing.  Note that such files may have been
generated by UPP as part of the current SRW App workflow, or they may be
user-staged. 
========================================================================"
#
#-----------------------------------------------------------------------
#
# Get the time lag for the current ensemble member.
#
#-----------------------------------------------------------------------
#
set -x
i="0"
if [ $(boolify "${DO_ENSEMBLE}") = "TRUE" ]; then
  i=$( bc -l <<< "${ENSMEM_INDX}-1" )
fi
time_lag=$( bc -l <<< "${ENS_TIME_LAG_HRS[$i]}*${SECS_PER_HOUR}" )
#
#-----------------------------------------------------------------------
#
# Get the list of forecast hours for which there is a post-processed 
# output file.  Note that:
#
# 1) CDATE (in YYYYMMDDHH format) is already available via the call to
#    the job_preamble.sh script in the j-job of this ex-script.
# 2) VAR is set to "APCP" and ACCUM_HH is set to "01" because we assume
#    the output files are hourly, so these settings will result in the
#    function set_vx_fhr_list checking for existence of hourly post output
#    files.
#
#-----------------------------------------------------------------------
#
ensmem_indx=$(printf "%0${VX_NDIGITS_ENSMEM_NAMES}d" $(( 10#${ENSMEM_INDX})))
ensmem_name="mem${ensmem_indx}"
FCST_INPUT_FN_TEMPLATE=$( eval echo ${FCST_SUBDIR_TEMPLATE:+${FCST_SUBDIR_TEMPLATE}/}${FCST_FN_TEMPLATE} )

FHR_LIST=$( python3 $USHdir/set_vx_fhr_list.py \
  --cdate="${CDATE}" \
  --fcst_len="${FCST_LEN_HRS}" \
  --field="$VAR" \
  --accum_hh="${ACCUM_HH}" \
  --base_dir="${VX_FCST_INPUT_BASEDIR}" \
  --filename_template="${FCST_INPUT_FN_TEMPLATE}" \
  --num_missing_files_max="${NUM_MISSING_FCST_FILES_MAX}" \
  --time_lag="${time_lag}") || \
print_err_msg_exit "Call to set_vx_fhr_list.py failed with return code: $?"
#
#-----------------------------------------------------------------------
#
# Print message indicating successful completion of script.
#
#-----------------------------------------------------------------------
#
print_info_msg "
========================================================================
Done checking for existence of post-processed files for ensemble member ${ENSMEM_INDX}.

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
