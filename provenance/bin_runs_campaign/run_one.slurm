#!/bin/bash -l
#SBATCH -A amannodi
#SBATCH --job-name=binph
#SBATCH -N 1
#SBATCH -n 96
#SBATCH -o /scratch/gautschi/rahma103/bin_runs/logs/%x_%j.out
module --force purge
module load intel/2024.1 impi/2021.12
module load vasp/6.4.3
POT=/home/rahma103/POTPAW/potpaw_PBE.54
cd /scratch/gautschi/rahma103/bin_runs/$1
rm -f POTCAR; while read p; do cat $POT/$p/POTCAR >> POTCAR; done < PAWS
if [ ! -s done.marker ]; then
  mpirun -np ${SLURM_NTASKS} vasp_std > outVASP 2>&1 && grep -q "F=" OSZICAR && touch done.marker
fi
# chained HSE+SOC static on the relaxed geometry
if [ -d soc ] && [ -s done.marker ] && [ ! -s soc/done.marker ]; then
  cp CONTCAR soc/POSCAR; cp POTCAR soc/
  cd soc
  mpirun -np ${SLURM_NTASKS} vasp_ncl > outVASP 2>&1 && grep -q "F=" OSZICAR && touch done.marker
fi
