# Provenance — recompute-from-raw cross-checks (2026-08-12)

Every published number was recomputed from raw VASP outputs on Purdue Anvil and diffed
against the shipped dataset. Raw data mirrored on ALCF Eagle (/wbg_defects/chalcogenide_defects/).

## Bulk compounds (6763, HSE06+SOC production tree)
- Total energy: OSZICAR final **F** (free energy; the production pipeline used F, not E0).
- Formation E/atom: (F − Σnᵢμᵢ)/N with the production ELEMENTAL_REF dict → **6763/6763 reproduce ≤ 6e-7 eV/atom**.
- Decomposition E/f.u.: stoichiometric binary decomposition + ideal-mixing entropy (kT = 0.0257 eV)
  with the production COMPOUND_REF dict → **6763/6763 reproduce ≤ 6e-7 eV**.
- Dielectric (electronic, LOPTICS E=0 density–density diag mean): **6762/6763 exact**, 1 outlier.
- Band gap: EIGENVAL band-counting with NELECT occupied bands (noncollinear) → gaps_bandcount.csv;
  **median Δ = 2.6e-5 eV vs shipped**; 162 rows differ >1 meV (under review — same vintage issue as SLME).
- SLME: max-over-thickness of SLME.dat Average(%) → **5834/6763 exact**; 929 stored values trace to an
  earlier SLME.dat vintage (575 files since deleted, 354 overwritten) — reproducible-in-method via
  vaspkit from the surviving IMAG.in/REAL.in/FERMI_ENERGY inputs, not from current files.

## CdSeTe defect library
- All Toten/Ef values on the site derive from the compiled generation CSVs; independent envelope
  recomputes verified per-row (V_Cd CdTe PBEsol 2.31/1.54 eV, HSE+SOC 3.25/2.13 eV; As_Se CdSe0.25 2.73 eV).
- Rows with Toten stored as 0.00 are failed calcs and are dropped per charge state.
- Finite-size corrections are Kumagai eFNV; the generating script and dielectric tensor are not
  archived — corrections are reproducible in-method (pydefect + literature ε), not bit-reproducible.

## A2BCX4 3x3x2 defect tree (PBEsol) — NOT yet published
Audit 2026-08-12: 3985 of 4916 charge-point runs finished, 931 unfinished (mid-relaxation, no final F);
energy-consistency failures remain even among finished pairs pending an INCAR/lattice audit.
This defect set enters the site only after that campaign completes.
