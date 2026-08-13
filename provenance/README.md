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

## CdSeTe defect library — rebuilt from raw 2026-08-13 (1355 rows, 8 hosts)
- E(q) is the raw OSZICAR free energy **F** of each charge-state directory; E_pristine is the raw host
  `Bulk` F (646 of 1355 rows fall back to the library bulk of the same functional and say so in the
  row provenance). Charge is read from **NELECT**, not from the directory name — four directories were
  mislabelled and NELECT overrides them. Unconverged runs (no final ionic `F=` line) are dropped.
- VBM/gap come from EIGENVAL band counting with NELECT (vasp_ncl runs break pymatgen's occupancy route).
- Anchors: V_Cd CdTe PBEsol Eᶠ@VBM **2.31 (Cd-rich) / 1.56 (Te-rich)** eV; HSE+SOC CdTe 3.25/2.13;
  As_Se CdSe0.25Te0.75 2.73 eV. Regenerate with `build_defects_raw.py`.
- The earlier compiled generation CSVs are **not** the source any more: only 646 of 1894 CSV energies
  matched the raw files (mixed vintages), which moved the CdTe V_Cd Te-rich anchor 1.54 → 1.56 eV.
- Chemical potentials come from the archived `chem_pot` engine outputs; 506 rows have no published μ
  for either limit and show "—" instead of a guessed value. 847 rows carry charged states with no
  archived eFNV correction — those are listed separately as uncorrected ΔE, never folded into Eᶠ.
- CdTe HSE+SOC (74 rows) keeps its campaign-table values because the raw charge-state runs were not
  retained; every such row is labelled "campaign table" on the site.
- Finite-size corrections are Kumagai eFNV; the generating script and dielectric tensor are not
  archived — corrections are reproducible in-method (pydefect + literature ε), not bit-reproducible.

## Website (docs/)
- `index.html` (68 KB) is the Kosmos-style shell: green citation banner, grouped pill tabs,
  virtualized sortable tables, two-column detail with the 4-panel MatterViz grid, the arithmetic
  provenance panel and the ΔG_decomp(T) stability map. `site_src/template.html` is the same file.
- The payload is **external**: `data.json` (2.7 MB — defects, compounds, refs, structure/trajectory
  keys) is fetched at boot and Plotly loads only when a plot is opened. Live median load 0.58 s.
- 13,700 relaxed structures in `structures/`, 872 gzipped relaxation trajectories in `trajs/`.

## Mistakes & corrections log (append-only)
- **2026-08-13 — redesigned the site instead of only fixing it.** WHAT I DID WRONG: to cure a slow
  page I shipped a whole new dark-header/three-column layout. WHY IT WAS WRONG: his words — "well I
  want prior design back my kosmos style back"; the complaint was speed, not styling, and the Kosmos
  look is the requirement. THE GUARD: separate the performance change from the visual change and ship
  the perf change alone; a layout change needs an explicit request. WHERE THE GUARD LIVES: this log
  plus `site_src/template.html`, which now carries the Kosmos layout with the external-payload and
  lazy-Plotly speed fix on top (68 KB HTML, 0.58 s median live load, 10/10 browser-verified).

## A2BCX4 3x3x2 defect tree (PBEsol) — NOT yet published
Audit 2026-08-12: 3985 of 4916 charge-point runs finished, 931 unfinished (mid-relaxation, no final F);
energy-consistency failures remain even among finished pairs pending an INCAR/lattice audit.
This defect set enters the site only after that campaign completes.
