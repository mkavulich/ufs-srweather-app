#!/bin/bash

# Start date and end date
start=20220501
end=20220506

# Loop over dates
current=$start
k=0
while [ "$current" -le "$end" ]; do
  k=$(($k + 1))
  echo "Processing date: $current"

  # Construct the directory path based on the current date
  dir_path="/scratch2/BMC/fv3lam/Vanderlei.Vargas/Agile/RRFS_GDAS/${current}00/metprd/ensemble_stat_cmn"

  # Check if the directory exists
  if [ -d "$dir_path" ]; then
    # Copy files with the pattern *ADPSFC*.stat to the current directory
    rm -rf /scratch2/BMC/fv3lam/Vanderlei.Vargas/Agile/usecase/INPUT/*
    cp -Rf ${dir_path}/*ADPSFC*.stat /scratch2/BMC/fv3lam/Vanderlei.Vargas/Agile/usecase/INPUT/.
    python reformat_ecnt_linetype.py reformat_ecnt.yaml 
    mv ./OUTPUT/ensemble_stat_ecnt.data ./OUTPUT/ensemble_stat_ecnt${k}.data
  else
    echo "Directory does not exist: $dir_path"
  fi


  # Increment the date by one day
  current=$(date -d "$current + 1 day" +"%Y%m%d")
done

