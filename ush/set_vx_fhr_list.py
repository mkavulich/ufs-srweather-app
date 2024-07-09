#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

def eval_METplus_timestr_tmpl(init_time, fhr, METplus_timestr_tmpl):
    yyyymmdd_init = init_time[:8]
    hh_init = init_time[8:10]

    mn_init = "00"
    if len(init_time) > 10:
        mn_init = init_time[10:12]

    ss_init = "00"
    if len(init_time) > 12:
        ss_init = init_time[12:14]

    init_time_str = f"{yyyymmdd_init} {hh_init}:{mn_init}:{ss_init}"
    init_time_dt = datetime.strptime(init_time_str, "%Y%m%d %H:%M:%S")
    valid_time_dt = init_time_dt + timedelta(hours=fhr)

    regex_search = r"^\{(init|valid|lead)(\?)(fmt=)([^\?]*)(\?)?(shift=)?([^\?]*)?\}"
    
    METplus_time_type = re.search(regex_search, METplus_timestr_tmpl).group(1)
    METplus_time_fmt = re.search(regex_search, METplus_timestr_tmpl).group(4)
    METplus_time_shift = re.search(regex_search, METplus_timestr_tmpl).group(7)

    if METplus_time_fmt in ["%Y%m%d%H", "%Y%m%d", "%H%M%S", "%H"]:
        fmt = METplus_time_fmt
    elif METplus_time_fmt == "%HHH":
        fmt = "%03.0f"
    else:
        raise ValueError(f"Unsupported METplus time format:\n  {METplus_time_fmt=}\n  {METplus_timestr_tmpl=}")
    
    time_shift_secs = int(float(METplus_time_shift or 0))
    time_shift_td = timedelta(seconds=time_shift_secs)
    
    if METplus_time_type == "init":
        formatted_time = (init_time_dt + time_shift_td).strftime(fmt)
    elif METplus_time_type == "valid":
        formatted_time = (valid_time_dt + time_shift_td).strftime(fmt)
    elif METplus_time_type == "lead":
        lead_secs = (valid_time_dt + time_shift_td - init_time_dt).total_seconds()
        lead_hrs = lead_secs / 3600
        
        lead_hrs_trunc = int(lead_hrs)
        lead_hrs_rem = lead_hrs - lead_hrs_trunc
        if lead_hrs_rem != 0:
            raise ValueError(f"The lead in hours ({lead_hrs=}) derived from seconds ({lead_secs=}) must be an integer")
        
        formatted_time = f"{lead_hrs_trunc:03d}"
    else:
        raise ValueError(f"Unsupported METplus time type:  {METplus_time_type=}")


    return formatted_time


def set_vx_fhr_list(cdate, fcst_len, field, accum_hh, base_dir, filename_template, num_missing_files_max, verbose=False,check_accum_contrib_files=False):
    """Generates a list of forecast hours such that for each hour there exist a corresponding file
    according to the filename pattern (filename_template) and other variables provided.

    Args:
        cdate      (str): Date string in YYYYMMDD[mmss] format, where minutes and seconds are
                          optional.
        fcst_len   (int): Length of forecast in hours
        field      (str): Field name; see the first if block for valid values
        accum_hh   (int): Accumulation period for the specified field. For instantaneous fields,
                          set to 1.
        base_dir   (str): Directory to find the paths to files specified by filename_template
        filename_template     (str): The METplus filename template for finding the files
        num_missing_files_max (int): If more files than this value are not found, raise exception
        verbose              (bool): By default this script only outputs the list of forecast hours
                                     (for easier parsing from bash contexts). Set the verbose flag
                                     to True for additional debugging output.
        check_accum_contrib_files (bool): If true, check all files contributing to accumulation
                                          period, not just forecast hours.
    Returns:
        fhr_list_str (str) : A comma-separated list of forecast hours where files were found
    """
    # Set the interval (fhr_int) and minimum (fhr_min) hours for observation files for a given
    # observation type and accumulation period/interval. For most observations and forecast fields
    # this is 1 and 0, respectively (indicating instantaneous obs available every hour). For
    # accumulation fields, you need a forecast length at least as long as the accumulation period,
    # so fhr_min=accum_hh. For files that are not hourly, but instead contain data for multiple
    # hours, they will need to have fhr_int specified accordingly.
    # Every valid verification field (valid_vals_VX_FIELDS in valid_param_vals.yaml) should have
    # an entry in this if block 
    if field == "AOD":
        fhr_min = 0
        fhr_int = 24
    elif field == "APCP":
        fhr_min = accum_hh
        fhr_int = accum_hh
    elif field == "ASNOW":
        if accum_hh == 24:
            fhr_min = 24
            fhr_int = 12
        else:
            fhr_min = accum_hh
            fhr_int = accum_hh
    elif field in ["PM25", "PM10", "REFC", "RETOP", "ADPSFC"]:
        fhr_min = 0
        fhr_int = 1
    elif field == "ADPUPA":
        fhr_min = 0
        fhr_int = 6
    else:
        raise ValueError(f"A method for setting verification parameters has not been specified for this field: {field=}")

    fhr_max = fcst_len
    fhr_array = list(range(fhr_min, fhr_max + 1, fhr_int))
    if verbose:
        print(f"Initial (i.e. before filtering for missing files) set of forecast hours is:\n  fhr_array = {fhr_array}")

    fhr_list = []
    num_missing_files = 0

    for fhr_orig in fhr_array:
        if check_accum_contrib_files:
            fhr = fhr_orig - accum_hh + 1
            num_back_hrs = accum_hh
        else:
            fhr = fhr_orig
            num_back_hrs = 1
        skip_this_fhr = False

        for _ in range(num_back_hrs):
            # Use the provided template to set the name of/relative path to the file 
            # Note that the while-loop below is over all METplus time string templates
            # of the form {...} in the template fn_template; it continues until all
            # such templates have been evaluated to actual time strings.
            fn = filename_template
            regex_search_tmpl = r"(.*)(\{.*\})(.*)"
            crnt_tmpl = re.search(regex_search_tmpl, filename_template).group(2)
            remainder = re.sub(regex_search_tmpl, r"\1\3", filename_template)

            while crnt_tmpl:
                actual_value = eval_METplus_timestr_tmpl(cdate, fhr, crnt_tmpl)
                crnt_tmpl_esc = re.escape(crnt_tmpl)
                fn = re.sub(crnt_tmpl_esc, actual_value, fn, 1)
                match = re.search(regex_search_tmpl, remainder)
                crnt_tmpl = match.group(2) if match else ''
                remainder = re.sub(regex_search_tmpl, r"\1\3", remainder)

            fp = os.path.join(base_dir, fn)

            if os.path.isfile(fp):
                if verbose:
                    print(f"Found file (fp) for the current forecast hour (fhr; relative to the cycle date cdate):\n  fhr = \"{fhr}\"\n  cdate = \"{cdate}\"\n  fp = \"{fp}\"")
            else:
                skip_this_fhr = True
                num_missing_files += 1
                if verbose:
                    print(f"The file (fp) for the current forecast hour (fhr; relative to the cycle date cdate) is missing:\n  fhr = \"{fhr}\"\n  cdate = \"{cdate}\"\n  fp = \"{fp}\"\nExcluding the current forecast hour from the list of hours passed to the METplus configuration file.")
                break

            fhr += 1

        if not skip_this_fhr:
            fhr_list.append(fhr_orig)

    fhr_list_str = ','.join(map(str, fhr_list))
    if verbose:
        print(f"Final (i.e. after filtering for missing files) set of forecast hours is (written as a single string):\n  fhr_list = \"{fhr_list_str}\"")

    if num_missing_files > num_missing_files_max:
        raise Exception(f'The number of missing files {num_missing_files} is greater than the specified {num_missing_files_max=}')
    
    return fhr_list_str

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Return a list of forecast hours such that there is a corresponding file (can be observations or forecast files) for each list entry.",
    )
    parser.add_argument("-v", "--verbose", help="Verbose output", action="store_true")
    parser.add_argument("-cd", "--cdate", help="Date in YYYYMMDDHH format", type=str, required=True)
    parser.add_argument("-fl", "--fcst_len", help="Forecast length in hours", type=int, required=True)
    parser.add_argument("-f", "--field", help="Field name", type=str, required=True,
                        choices=["PM25", "PM10", "REFC", "RETOP", "ADPSFC", "AOD", "APCP", "ASNOW", "ADPUPA"])
    parser.add_argument("-a", "--accum_hh", help="Accumulation length in hours for the specified field. For example, for 6-hour accumulated precipitation, field=APCP, accum_hh=6", type=int, default=1)
    parser.add_argument("-bd", "--base_dir", help="Base directory for forecast/observation file", type=str, default='')
    parser.add_argument("-ft", "--filename_template", help="Template for file names to search; see ??? for details on template settings", type=str, required=True)
    parser.add_argument("-n", "--num_missing_files_max", type=int, default=5,
                        help="Number of missing files to tolerate; if more files than this number can not be found, raise an exception")
    parser.add_argument("--check_accum_contrib_files", action="store_true",
                        help="Flag that determines whether we check the initial time of the accumulation period or not") 

    args = parser.parse_args()

    vx_fhr_list = set_vx_fhr_list(**vars(args))
    print(vx_fhr_list)
