#!/bin/bash -l
#SBATCH -A amannodi
#SBATCH --job-name=binq
#SBATCH -N 1
#SBATCH -n 96
#SBATCH -t 6:00:00
#SBATCH -o /scratch/gautschi/rahma103/bin_runs/logs/%x_%j.out
module --force purge
module load intel/2024.1 impi/2021.12
module load vasp/6.4.3
POT=/home/rahma103/POTPAW/potpaw_PBE.54
for d in pbe_ZnS pbe_CdS pbe_In2S3 pbesol_SnTe2 pbesol_GeTe2; do
  cd /scratch/gautschi/rahma103/bin_runs/$d
  [ -s done.marker ] && continue
  rm -f POTCAR; while read p; do cat $POT/$p/POTCAR >> POTCAR; done < PAWS
  mpirun -np ${SLURM_NTASKS} vasp_std > outVASP 2>&1 && grep -q "F=" OSZICAR && touch done.marker
done
# free slot used well: launch Cu2Se once the quick batch is done
sbatch -p highmem -n 96 -t 24:00:00 /scratch/gautschi/rahma103/bin_runs/run_one.slurm soc_Cu2Se
