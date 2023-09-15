#!/bin/bash

set -u

fcst_init_first="2022050100"
num_fcsts="12"
fcst_init_intvl="24"
fcst_len_hrs="36"
base_dir="/home/ketefian/ufs-srweather-app/ush/python_utils/metviewer/mv_output"
models="href gdas gefs"
num_ens_mems="10 10 10"

#set -x

#auc:
#    apcp:
#        03hr:
#            thresholds: ['gt0.0mm', 'ge2.54mm']
#    dpt:
#        2m:
#            thresholds: ['ge288K', 'ge293K']
#    refc:
#        L0:
#            thresholds: ['ge20dBZ', 'ge30dBZ', 'ge40dBZ', 'ge50dBZ']
#    tmp:
#        2m:
#            thresholds: ['ge293K', 'ge298K']
#        850mb:
#            thresholds: ['ge288K']
#    wind:
#        10m:
#            thresholds: ['ge5mps', 'ge10mps']
#        700mb:
#            thresholds: ['ge10mps']

stats=('auc' 'bias' 'brier' 'fbias' 'rely' 'rhist' 'ss')

for (( istat=0; istat<${#stats[@]}; istat++ )); do

  stat="${stats[$istat]}"
  printf "\n"
  printf "stat = %s\n" "${stat}"

  if [ "${stat}" = 'auc' ]; then
    fcst_vars=('apcp' 'dpt' 'refc' 'tmp' 'wind')
  else
    fcst_vars=()
  fi

  for (( ifcst=0; ifcst<${#fcst_vars[@]}; ifcst++ )); do
  
    fcst_var="${fcst_vars[$ifcst]}"
    printf "\n"
    printf "  fcst_var = %s\n" "${fcst_var}"

    if [ "${fcst_var}" = 'apcp' ]; then
      levels=('03hr')
    elif [ "${fcst_var}" = 'dpt' ]; then
      levels=('2m')
    elif [ "${fcst_var}" = 'refc' ]; then
      levels=('L0')
    elif [ "${fcst_var}" = 'tmp' ]; then
      thresholds=('2m' '850mb')
    elif [ "${fcst_var}" = 'wind' ]; then
      thresholds=('10m' '700mb')
    fi

    for (( ilvl=0; ilvl<${#levels[@]}; ilvl++ )); do
    
      level="${levels[$ifcst]}"
      printf "\n"
      printf "    level = %s\n" "${level}"
  
      if [ "${level}" = '03hr' ]; then
        thresholds=('gt0.0mm' 'ge2.54mm')
      elif [ "${level}" = '2m' ]; then
        thresholds=('ge20dBZ' 'ge30dBZ' 'ge40dBZ' 'ge50dBZ')
      fi
#  
#    for (( ithresh=0; ithresh<${#thresholds[@]}; ithresh++ )); do
#      thresh="${thresholds[$ithresh]}"
#      ./generate_metviewer_xmls.py \
#        --fcst_init ${fcst_init_first} ${num_fcsts} ${fcst_init_intvl} \
#        --fcst_len_hrs ${fcst_len_hrs} \
#        --models ${models} \
#        --num_ens ${num_ens_mems} \
#        --stat auc \
#        --fcst_var REFC \
#        --level_or_accum L0 \
#        --threshold ${thresh} \
#        --metviewer_output_dir ${base_dir}
#    done
  
  done

done
