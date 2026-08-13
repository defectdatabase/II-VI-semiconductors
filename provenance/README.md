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

## A2BCX4/ABX2 HSE06 campaign — restored from archive 2026-08-13 (LIVE)
- Source: `gautschi_scratch_2026-05-26.tar` → `Projects_22_May_2025/A2BCX4_ABX2/hse/2x2x1/bulk`
  (7,049 dirs, 937 GB) extracted on Anvil; references `A2BCX4_ABX2_v1/reference/HSE` (identical INCAR
  family: LHFCALC, AEXX 0.25, HFSCREEN 0.2, GGA=PS, ENCUT 400, ISIF 3, EDIFFG -0.05).
- Published: **3,531 converged relaxations over 2,433 compounds** (runs whose OSZICAR ends on an
  ionic F line; 3,518 unconverged/incomplete dirs excluded). eform from raw F with same-theory raw
  elemental mus; edec versus same-theory binaries per f.u.; gaps by NELECT band counting on EIGENVAL
  with the occupancy column as an independent cross-check (3,229/3,552 agree exactly; smeared-edge
  cases resolved by the NELECT convention; 3 hand-checked).
- Anchor cross-checked by a second, fully independent route on Anvil (direct OSZICAR/CONTCAR reads):
  Cu2ZnSnS4 kesterite eform -0.598699 eV/atom, edec -0.679923 eV/f.u., gap 1.4397 eV — exact match.
- GeTe2/SnTe2 are not archived in ANY reference tree, so (Ge|Sn)+Te kesterites keep edec blank —
  disclosed in the row provenance, never mixed across theories. No LOPTICS in this campaign →
  dielectric/SLME blank. 3,531 relaxed structures + 3,169 relaxation movies published.
- Sweep scripts: `sweep_hse2x2x1.py`, `gaps_hse2x2x1.py`, `hse_struct_traj.py` (Anvil
  `defectdb_recompute/`).

## II-VI alloy pseudo-binary decomposition (2026-08-13)
- 27 II-VI alloy rows (CdSeTe / CdZnTe at PBEsol/PBE/HSE06/HSE06-noPS) now carry
  edec = E/f.u. - Sum f*E(end-member binary) + kT*Sum f ln f, with end-member energies taken from the
  SAME library's binary rows (never the A2BCX4 reference trees — the two HSE trees differ by
  0.06-0.42 eV/atom in elemental mus and must not be mixed). Mixing entropy stored per row (index 9)
  drives the dG(T) stability map.

## Website (docs/)
- Stability-map section shows on every compound: real dG_decomp(T) map with labeled contours (red
  contour at dG=0 when it crosses), or an explicit note when no binary decomposition is archived.
- Table: No. of atoms + Lattice parameter columns (Supercell column removed), "Dielectric constant"
  label, Compounds Explorer tab name; compound-modal download buttons removed on request; modal
  columns bottom-aligned (flex-grow noteboxes).
- `index.html` (68 KB) is the Kosmos-style shell: green citation banner, grouped pill tabs,
  virtualized sortable tables, two-column detail with the 4-panel MatterViz grid, the arithmetic
  provenance panel and the ΔG_decomp(T) stability map. `site_src/template.html` is the same file.
- The payload is **external**: `data.json` (2.7 MB — defects, compounds, refs, structure/trajectory
  keys) is fetched at boot and Plotly loads only when a plot is opened. Live median load 0.58 s.
- 13,700 relaxed structures in `structures/`, 872 gzipped relaxation trajectories in `trajs/`.

## UI pass 2026-08-13 (user-directed, all browser-verified live 10/10)
- MatterViz panes forced white (`--page-bg`/`--pane-bg` — the bundle hardcodes `--page-bg:#090019`);
  control/info/export panes escape the small grid cells (overflow visible), capped 340px, scroll inside.
- HSE06 (no PS) merged into HSE06: 5 duplicate II-VI rows dropped (GGA=PS row kept), 4 alloy-only rows
  relabeled with a structure-key override (`fk:"hse_no_ps"`) so their geometries still resolve.
- Modal: theory suffix out of the title, provenance and map notes without gray cards, justified text,
  both bottom sections scroll so the two columns end level; static rows say "static run (NSW = 0) on
  the relaxed geometry" (verified on disk: XDATCAR has 1 configuration — no movie is possible there).
- Table: Compounds Explorer tab, No. of atoms + Lattice parameter columns, "Dielectric constant",
  sentence-case filter labels, search inputs with icon, crisp selects, download buttons removed.

## Full-transparency pass 2026-08-13 PM (user-directed; all raw-derived, nothing recalled)
- Per-ordering payload extended: VBM/CBM from occupied-band counting (16,648), eps diagonal
  components from REAL.in (6,188), SLME(thickness) curve + optimum and 14-point absorption sample
  from vaspkit outputs (6,188), static-frame Fmax from OUTCAR TOTAL-FORCE (13,126), per-run k-mesh
  from KPOINTS (16,657), verified POTCAR TITEL sets per tree (S POTCAR not archived in the II-VI
  library -> not quoted). 438 missing HSE+SOC structures extracted; HSE06 (no PS) merged into HSE06.
- Provenance panel now walks every number step by step; calculation-inputs popup is per-compound
  (supercell, this run's k-mesh, POTCAR titles, final F). Relaxation-movie button on every row —
  statics play their one archived configuration with E and Fmax.
- The P-T stability map was replaced (pressure axis carries no information for a balanced solid-state
  decomposition): element-projected DOS (DOSCAR sweep) with a dG_decomp(T) line fallback.

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
