#Setup instructions for MSU Orion using Intel-19.1.0.166 (bash shell)

module purge
module load intel/2020
module load impi/2020
module load cmake/3.15.4

export CC=icc
export CXX=icpc
export FC=ifort
export Jasper_ROOT=/apps/jasper-1.900.1

module use /work/noaa/gmtb/dheinzel/NCEPLIBS-ufs-v2.0.0/intel-19.1.0.166/impi-2020.0.166/modules

module load netcdf/4.7.4
module load esmf/8.0.0

module load bacio/2.4.1
module load crtm/2.3.0
module load g2/3.4.1
module load g2tmpl/1.9.1
module load ip/3.3.3
module load nceppost/dceca26
module load nemsio/2.5.2
module load sp/2.3.3
module load w3emc/2.7.3
module load w3nco/2.4.1

module load gfsio/1.4.1
module load sfcio/1.4.1
module load sigio/2.3.2
module load wgrib2/2.0.8

export CMAKE_C_COMPILER=mpiicc
export CMAKE_CXX_COMPILER=mpiicpc
export CMAKE_Fortran_COMPILER=mpiifort
export CMAKE_Platform=orion.intel

mkdir build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX=..
make -j 4
