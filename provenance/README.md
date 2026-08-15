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

## DOS + optics pass 2026-08-13 (late PM)
- Element-projected DOS published for 16,809 rows/orderings from raw DOSCARs (per-atom orbital
  projections summed by element, 160-point window around E_F): HSE+SOC 100%, PBEsol 92%, all 223
  reference phases. The HSE06 A2BCX4 campaign ran without LORBIT, so no projections exist on disk —
  its 3,427 rows show the TOTAL DOS parsed from vasprun.xml and the panel says so. Remaining rows
  (388 PBEsol + 160 HSE06) have no matching raw run and keep the dG_decomp(T) line.
- Boot payload trimmed back to 5.1 MB: SLME(thickness) + absorption arrays moved to a lazily
  fetched optics.json.gz; per-row DOS fetched on demand (docs/dos/, 53 MB gzipped).
- WebGL context parking (dashboard viewers released while a movie is open) cured the hangs —
  browsers grant ~8 contexts and two open 4-pane grids exhausted them.
- Axis views are orthographic projections sighted down the cell vectors (labeled Along a/b/c).
- Sweep scripts: dos_sweep.py, ref_dos_sweep.py, hse06_dos_sweep.py (Anvil defectdb_recompute/).

## Defect-modal transparency + reference-design pass (2026-08-13 late)
- Defect modal: per-vertex sigma blocks (E_defect,q / E_corr / dE / Ef@VBM per charge, not-run rows,
  q=0 arithmetic check), typewriter-paced and scrollable, ending with the FULL chem-pot solution:
  archived vertex tables (limit, delta-mu, absolute mu per element) and every archived competing
  phase's raw F / atoms / E-per-atom (95 PBEsol + 96 HSE+SOC runs; docs/chempot.json.gz, built by
  chempot_sweep.py from the chem_pot trees; alloy hosts mapped from Cd108SeXTeY supercell names).
- Formation-energy plot: single envelope for the selected growth condition (vertex-labeled dropdown),
  open-circle transition kinks, dotted uncorrected context lines, VBM/CBM bands; transition-level
  ladder with shallow/deep character (hidden when no corrected charged states exist).
- Viewers: panes are true orthographic projections aimed at the cell centre (camera_target) —
  Perspective/Front/Top/Right everywhere; defect species rendered black (element_colors); right
  column falls back to the relaxed host supercell when a defect kept no ionic steps.
- Movie: Kosmos layout, all four panes animate via double-buffered swaps retired after paint
  (no flash), panes clipped and width-bounded; per-frame E / dE / F max readout.
- Payloads split for speed: data.json 5.1 MB at boot; optics.json.gz, chempot.json.gz and per-row
  dos/*.json.gz fetched on demand.

## Trajectory viewer on MatterViz + density pass (2026-08-14, user-directed)

- `site_src/traj.html` — the relaxation-movie pane — no longer draws its own 2D canvas (private
  COLORS/RADII tables, hand-rolled yaw/pitch projection, bonds only for cells ≤128 atoms, so the
  216-atom defect supercells rendered as a flat dot cloud). It now mounts the **same MatterViz
  bundle at the same pinned revision** the parent page uses, so every structure view on the site
  comes from one renderer: bonds, coordination polyhedra, MatterViz's own element legend and
  supercell control, and the same white-pane variables.
- Playback steps one stored ionic frame per tick (380 ms) and keeps the double-buffered swap: the
  next frame is built in a hidden buffer while the current one is on screen, then whole buffers are
  exchanged and the retired one has its WebGL context released. Measured mount cost 3 ms per frame
  (216 atoms); the DOM holds at most two buffers, so the ~8-context browser budget is never spent.
- Defect highlighting travels in the payload as `dark` (element_colors) instead of `dsite`
  fractional coordinates — MatterViz colours by element, and the parent already computes that map
  for the dashboard panes. The canvas-only exact-site marker is therefore gone; for defects built
  from host species alone the colour route cannot mark one site, which is what the defect-structure
  heading has always said.
- The readiness/paint waits resolve on `requestAnimationFrame` **or** a 60 ms timer, whichever
  fires first: an occluded tab freezes rAF entirely, and the first implementation stalled at frame 1
  in exactly that case. Playback additionally **holds while `document.hidden`** and repaints the
  current frame on `visibilitychange`, because the timer fallback would otherwise promote a buffer
  WebGL had not drawn and the pane read white on return (seen live on r83f1cc72, fixed in r01f4dffd).
- Live on GitHub Pages at commit **01f4dffd**; `traj.html` is served `cache-control: max-age=600`,
  so a browser that already loaded the old pane keeps it for up to ten minutes.
- Density pass in `template.html` (one appended block; no layout, palette or component change):
  chrome above the table 318 → **254 px** and rows in view 15 → **22** at 1440×900 (row 34 → 26 px,
  table viewport `min(66vh,760px)`). Both detail modals now fit without an inner scrollbar
  (defect 930×571, compound 1080×737 measured). Verified live in the browser: all four tabs, both
  modals, tablet width (no page-level horizontal overflow), and the movie opened 10 times over
  three different trajectories — **10/10** mounted a MatterViz canvas with populated metrics.
  Frame-cadence timing could not be logged from the automation pane, which reports
  `visibilityState: "hidden"` outside the screenshot instant and so clamps its timers.

## Viewer pane sizing, defect-site marker, control colour (2026-08-14 PM, user-directed)

- **Modal dead space.** `#detail .dgrid` gave the left column `1fr` and hard-capped the right at
  360 px, so all spare width opened as an empty band down the middle of the modal. Tracks are now
  `fit-content(430px) minmax(0,1fr)`: the left track shrinks to the arithmetic tables and every spare
  pixel goes to the plot and viewer. Measured at 1280 px — left 430, right **360 → 456**, and the
  only space between the columns is the 14 px grid gap.
- **Trajectory pane was letterboxed.** MatterViz's root carries its own default height, so inside the
  movie pane it rendered 431×**500** in a 431×397 box with a 600×300 drawing buffer — the cell sat low
  and off-centre. `.mvbuf>*{width:100%!important;height:100%!important}` pins it to the pane;
  measured root 497×397 in a 497×397 pane.
- **The "defect species in black" claim was never true.** This prebuilt MatterViz build honours no
  per-site or per-element colour from props: `element_colors` belongs to its **trajectory-line**
  component (verified in the bundle: `U(t,'element_colors',...)` sits beside `trail_frames`/
  `wrap_mode`, and the structure viewer reads atom colours from a private `Vesta`-scheme store);
  `atom_color_config`'s `custom` mode passes `color_fn` return values through a D3 **categorical
  palette**, so it cannot force one site black while keeping element colours; and `active_sites` +
  `active_highlight_color` produced no visible change (A/B tested with `#ff0000` on a 2-atom cell).
  `site_radius_overrides` (Map of site index → radius) **does** work — A/B verified. The defect site
  is therefore drawn **oversized (2.6×)** with element colours intact, in the dashboard pane and in
  the movie, and the heading now reads "defect site drawn oversized" instead of claiming black.
  Site selection is by defect species, so host-species defects (e.g. Cd_Se) still cannot be pinned
  from composition alone — same limit the old canvas had.
- **Controls carry the tab accent.** Play/Pause is filled `#087f8c` with white text, the slider
  accent, frame counter and metric values are the same teal; only the metric labels stay muted grey.

## Movie viewer, defect-site detection, modal columns (2026-08-14 late, user-directed)

- **The movie no longer mounts MatterViz, and here is the measured reason.** The pinned bundle takes
  `structure` as a plain non-reactive prop, exposes no bindable `camera_position`/`rotation`/`scene`
  (tested: a props object with setters received **0 write-backs**), `window.__THREE__` is only a
  revision string, and no trajectory prop exists on the mounted root. Playing frames therefore means
  remounting, and every remount re-fits the camera — the user's zoom and rotation were thrown away
  between frames ("if I zoom in for new frame it goes back to old state"). The pane now draws its own
  scene with a camera we own: drag to rotate, wheel to zoom, shift-drag to pan, double-click to reset,
  and the view is untouched when the frame changes. Static structure panes keep MatterViz, where
  nothing remounts and the zoom already persisted.
- Atoms are shaded spheres with depth-scaled radii, bonds are depth-shaded, and the **defect site is
  painted black with a ring** — which the MatterViz build has no prop for at all.
- **Bond cutoff was wrong in the original canvas too:** `1.15-1.2 x` summed radii tops out at 2.46 A
  and a Cd-Te bond is 2.80 A, so no bond ever drew and the cell rendered as loose dots. Now `1.35 x`,
  capped at 3.3 A.
- **Defect sites are found geometrically, not by species.** `Cd_Se+Te_i` is built entirely from host
  elements, so the species rule marked nothing — which is why the user still saw no defect site. The
  defect cell is now matched against the relaxed host supercell: no host atom within 1.2 A means an
  interstitial, a different nearest element means an antisite or substitution, and more than six hits
  means the match drifted (species fallback). Measured: `Cd_Se+Te_i` -> **2 sites** (indices 203, 204),
  `V_Cd+Cd_Se` -> **1 site** (193; the vacancy has no atom to mark, and the heading says so).
- **"No atom moving" was the data, not the viewer.** For `Cd_Se+Te_i` the largest displacement across
  all 7 stored frames is **0.034 A** (mean 0.001 A) - the run was already converged (2.10 meV, F_max
  0.008 eV/A). The summary line now quotes it: "largest atom displacement 0.03 A", and prints
  "under 0.01 A - already converged" below 0.005 A. `V_Cd+Cd_Se` by contrast moves **0.93 A** over 40
  ionic steps, which is plainly visible.
- **Modal columns are proportional** (`minmax(0,.95fr) minmax(0,1.05fr)`). The previous
  `fit-content(430px)` left track was a fixed 430 px that pushed the right column over whenever the
  tables needed less. Measured at an 818 px modal: 368 / 406 with the tables filling 362.
- **The relaxation-movie button matches the close button** - white ground, 1 px border, `4px 12px`,
  13 px, measured 29 px tall against close's 30 px - instead of a filled teal pill.

## Kosmos viewer vendored verbatim (2026-08-14, user-directed: "follow Kosmos exactly")

Read out of `defect-informatics/kosmos` (private, Pages disabled — hence the 404; the repo is still
readable with `gh`) at `pages/traj/assets/index-B7HlPx2T-v2i.js`. Its exact viewer contract:

- frames arrive as **`{cif, energy, fmax}`** — CIF text per frame, parsed in the viewer — plus a
  **`dsite`** list of fractional coordinates and a `name`, over the same `traj_frames` postMessage.
- the viewer **recentres** every frame so `dsite[0]` sits at the cell centre, then takes the nearest
  site to each dsite **within 4.5 A** as `highlights`.
- it renders `<Structure>` with **`site_radius_overrides = Map(highlights -> 1.5)`** and
  **`scene_props = {active_sites: highlights, active_highlight_color: "#000"}`**, `show_controls:false`,
  `style="height:100%;background:#fff"`, `multi_view` bound (the four Perspective/Front/Top/Right panes).
- the camera survives frame changes because it **mutates one structure object in place** (`__wd` state,
  `__wr` writer) instead of remounting, and its MatterViz carries a `scene_props.preserve_camera` patch
  (`preserve_camera||(camera_target=void 0,camera_position=[0,0,0])`).

`docs/pages/traj/` is those 13 files copied unchanged (MatterViz + draco/basis/moyo wasm, 5.4 MB), so
its settings, theme and background are the reference's. The parent emits P1 CIF per frame and dsite
from the geometric defect/vacancy sites; my hand-written canvas viewer is deleted.

**Verified side by side (local, 1240x800):** Kosmos's page standalone fed our
`V_Cd+Cd_Se in CdSe0.20Te0.80` trajectory, and the same viewer inside our modal — both render four
panes with the **black defect atoms centred**, the "defect site highlighted" note, the
Se22/Cd106/Te87 legend and the ΔE-vs-final / F-max chart. Still open before this can be called a
100% match: the **static** structure panes (defect and compound detail) still mount this repo's older
prebuilt bundle, which does not forward `scene_props.active_sites`, so they mark the site by radius
only.

## Every structure pane now runs Kosmos's own viewer (2026-08-14, verified against the reference)

Both Kosmos apps are vendored unchanged from `defect-informatics/kosmos` (private, Pages disabled;
read with `gh`): `docs/pages/traj/` (13 files, 6.1 MB) drives the relaxation movie and
`docs/pages/structgrid/` (12 files, 4.3 MB) drives the defect and compound structure panes. Nothing
of ours renders atoms any more, so their MatterViz settings, theme and background are the
reference's by construction.

Contracts, read out of the Kosmos bundles:
- **movie** - `{type:"traj_frames", frames:[{cif, energy, fmax}], dsite, name}` after
  `{type:"traj_ready"}`; it recentres each frame on `dsite[0]`, highlights the nearest site to each
  dsite within 4.5 A, and renders with `site_radius_overrides Map(idx -> 1.5)` and
  `scene_props {active_sites, active_highlight_color:"#000"}`.
- **structure** - `{type:"struct", cif, bulkCif, nparts}` after `{type:"structgrid_ready"}`; it
  derives the marked sites itself by comparing the defect CIF against `bulkCif`, keeping `nparts`,
  and renders with `scene_props {active_sites, active_highlight_color:"#000000"}`,
  `show_controls:true`, `background_color:"#ffffff"`, four-pane `multi_view`, updating positions in
  place when the atom ordering matches so its camera survives.

**Snapshot comparison (live GitHub Pages, same defect `V_Cd+Cd_Se in CdSe0.20Te0.80`):** the
standalone `pages/structgrid/index.html` and our defect pane were fed the identical CIF - string hash
**3635253991**, `nparts:2` - and both render 4 canvases, the legend `Se22 Cd106 Te87`, the
`1 x 1 x 1` supercell control, the Perspective/Front/Top/Right panes and **2 black defect sites**.

## "No atom moving" - diagnosed and fixed (2026-08-14, live)

Measured on the live site, not inferred. The viewer and its play loop were working: the readout
advanced 1 -> 9 -> 12/12 while the tab was in the foreground (an automation probe with the tab hidden
freezes requestAnimationFrame and reports a frozen movie - that artifact cost one round of
misdiagnosis). Three real reasons the motion was invisible:

1. Kosmos's viewer plays the trajectory **once** at 700 ms/frame and parks on the last frame -
   12 frames is 8.4 s, so anyone who looked up a moment late saw a still picture.
2. An ionic relaxation puts nearly all displacement in the **first** frames: `V_Cd+Cd_Se` moves
   0.93 A in total, but frames 10-12 are converged and render identically.
3. Many rows are converged outright - `Cd_Se+Te_i` moves **0.034 A** across all 7 stored frames
   (mean 0.001 A, 2.10 meV, F_max 0.008 eV/A). No renderer can show that, which is why the summary
   strip now quotes the largest displacement per trajectory.

Fix: a parent-side watchdog restarts playback whenever the viewer is parked on the final frame, and
is cleared when the modal closes. Verified live - parked at frame 12/12, then back to **frame 1 / 12
with dE +0.68 eV, F max 0.45 eV/A**, playing.

## Formation-energy plot: clipped axis and degenerate y-range (2026-08-14)

The width was never reduced - the density pass widened the right column from 360 to 456 px at
1280 px. What the density pass did reduce was the plot's **height**, 235 -> 210 px, while the Plotly
layout still carried a hard `height:235` inside an `overflow:hidden` box: the bottom 25 px, i.e. the
second line of the `0.0 / VBM` and `<gap> / CBM` ticks plus the `Fermi level E_F (eV)` title, was cut
off. The layout height now follows `box.clientHeight`, the container is 252 px and the bottom margin
56 px. Measured: box 465x252, plot svg 465x252, **0 of 2 tick labels clipped** (label bottoms 408 vs
container bottom 433).

A flat envelope also autoscaled to a few meV (0.738-0.740 eV in the user's screenshot), which reads
as structure where there is none. The y-axis now holds a **0.2 eV minimum span** centred on the
value - measured [0.576, 0.816] for Sb_Te+Cl_Te - so a horizontal envelope looks horizontal.

## Formation-energy plot aspect (2026-08-14, follow-up)

Widening the modal fixed the clipping but left the plot at 596 x 252 - a **2.37:1 band**, in which a
flat envelope reads as a ruled line. Height raised to 380 px, so the plot is **596 x 380, aspect
1.57**, near the 3:2 a formation-energy diagram usually carries. Height rather than a narrower box
on purpose: capping the width would re-open the dead space beside the plot that was removed earlier.
Measured at a 1400 px window: modal 1180 x 855 with no inner scrollbar, structure pane still 340 px,
0 of 2 tick labels clipped.

## Formation-energy plot readability + movie caption subscripts (2026-08-14)

- **"The plot is a mess" was a flat envelope, not a bug.** For `Sb_Te+Cl_Te` in CdTe (PBEsol,
  Cd-rich) the envelope is **q = 0 at 0.740 eV across the entire gap**, with the only transition,
  (+1/0), at **E_F = 0.005 eV** - i.e. sitting on the valence-band edge. Autoscaling then gave a
  2 meV y-window, so a physically horizontal line looked like noise.
- The plot now states what it is doing: an annotation names the charge state that holds the envelope
  over >=90% of the gap and lists every transition level, flagging any within 15 meV of an edge as
  "(at the VBM)"/"(at the CBM)". Measured: `Sb_Te+Cl_Te`/CdTe -> "q = 0 lowest across the gap .
  eps(+1/0) = 0.00 eV (at the VBM)"; `Bi_Te+O_Te` -> "eps(+1/0) = 0.02 eV . eps(0/-1) = 0.34 eV .
  eps(-1/-2) = 0.51 eV".
- **Width**, since it was asked directly: the plot was never narrowed. It went 360 px (pre-density)
  -> 456 px (proportional columns) -> **596 px** now, by widening the defect modal from 930 to
  1180 px; the columns measure 540 / 596 at a 1400 px window and 0 of 2 tick labels clip.
- **Movie caption subscripts:** the payload carried `mvm-title.textContent`, which strips the `<sub>`
  markup, so Kosmos's caption read "BiTe+OTe in CdSe0.20Te0.80". Its caption is rendered as HTML
  (`fl(node, () => p(name), true)`, where `p()` maps `X_Y` to `X<sub>Y</sub>`), so it now receives
  `innerHTML` and renders "Bi_Te+O_Te in CdSe(0.20)Te(0.80)" with real subscripts.

## Every viewer on the Kosmos frame; movie modal enlarged (2026-08-14, late)

- **Static-calculation modal rendered an empty box** - a regression I introduced: `mvmMount` still
  called the locally built bundle after I deleted `docs/mv/`, so its dynamic import 404'd and the
  pane stayed blank. It, the in-page trajectory panel and `mvmShow` now all go through the same
  `sgShow` Kosmos frame. Verified: `Static calculation / SrS` renders **4 panes**, legend
  `S 1 x Sr 1`, `1 x 1 x 1`, Perspective/Front/Top/Right. `renderMatterViz` and `MV_BASE` no longer
  appear anywhere in the built page (grep count 0) - this page mounts no viewer of its own.
- **Movie modal** enlarged from 1240x800 to `min(1640px, 100vw-24px) x min(960px, 100vh-24px)` so
  Kosmos's four-pane grid fills the frame instead of floating in it.
- **One deliberate deviation from the vendored bundle**, logged here because everything else is
  byte-identical: the trajectory chart's tick formatter was fixed at 2 decimals
  (`T=(I,N)=>N>=100?I.toFixed(1):I.toFixed(2)`), so a run whose dE range is a few meV printed
  **0.00 on every left-axis tick**. It is now adaptive on the axis range - 4 decimals below 0.02 eV,
  3 below 0.2 eV, otherwise unchanged.

## Mistakes & corrections log (append-only)
- **2026-08-14 - deleted a bundle that three viewers still imported.** WHAT I DID WRONG: after moving
  the structure panes onto Kosmos's app I removed `docs/mv/`, but the static-calculation modal, the
  in-page trajectory panel and `mvmShow` still called `renderMatterViz` from it, so the user opened a
  static compound and got an empty white box -> THE GUARD: after removing a bundle, grep the built
  page for every symbol it exported (`renderMatterViz`, `MV_BASE`) and expect **zero** hits, then open
  one modal of each kind - defect, compound, static, movie -> GUARD LIVES IN this log and the grep
  in the publish routine.
- **2026-08-14 - overrode the reference's own defect detection.** WHAT I DID WRONG: after vendoring
  Kosmos's structgrid I still passed my own `highlight` index list, which takes priority over its
  bulk comparison, so our pane marked one site where the reference marked two on the identical CIF
  -> THE GUARD: when a vendored reference computes something itself, send it only its inputs
  (`bulkCif` + `nparts`) and compare the rendered result against the standalone app before believing
  the integration matches -> GUARD LIVES IN this section and `mountDefectStructure`'s `sgShow` call.
- **2026-08-14 — passed `active_sites` at the top level and concluded MatterViz could not highlight a
  site.** WHAT I DID WRONG: my A/B test put `active_sites`/`active_highlight_color` in the props root,
  saw no colour change, and I wrote in this file that the bundle "has no per-site colour hook", then
  built a whole hand-written canvas viewer on that premise. Kosmos passes both **inside `scene_props`**
  → THE GUARD: when a reference implementation exists, read ITS call site before concluding a feature
  is missing — `grep` the reference bundle for the prop and copy the nesting, do not infer it from a
  type list → GUARD LIVES IN this section and the vendored `docs/pages/traj/`.
- **2026-08-14 — shipped a MatterViz pane without checking the prop was real.** WHAT I DID WRONG: I
  carried `element_colors` over from the old code into the new trajectory pane and wrote "defect
  species in black" in the provenance, without ever confirming the structure viewer reads that prop —
  it does not, and the user reported "where is black site? I do not see it at all" → THE GUARD: before
  claiming a viewer prop works, grep the bundle for how it is consumed AND A/B render it with a
  garish colour on a 2-atom cell; a prop that Svelte silently ignores looks exactly like a prop that
  works → GUARD LIVES IN this log and the `defectSiteMark()` comment in `template.html`/`traj.html`.
- **2026-08-14 — pushed a frame swap that could show a white pane.** WHAT I DID WRONG: the MatterViz
  trajectory rewrite promoted each new frame buffer after a paint wait that falls back to a plain
  timer, so in an occluded tab (rAF frozen) it promoted a canvas WebGL had never drawn; the first
  live screenshot after the push caught exactly that blank pane mid-playback → THE GUARD: pause
  playback on `document.hidden` and repaint on `visibilitychange`, and screenshot the live page
  DURING playback, not only after it settles — a single after-the-fact frame hides transients →
  GUARD LIVES IN `site_src/traj.html` (`visibilitychange` handler) and this log.
- **2026-08-13 — repeatedly shipped UI changes the user had to reject** (duplicate movie chart,
  a second borrowed-DOS panel, monospace font as "typewriter", pane header strips): WHAT WAS WRONG —
  each was my interpretation layered on top of an explicit reference (the Kosmos site) instead of
  copying the reference exactly. THE GUARD — when a reference site/recording exists, reproduce it
  element-for-element and change nothing else without asking; a complaint about one element is not
  licence to restyle its neighbours. WHERE THE GUARD LIVES — this log.
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

## Defect-modal envelope + movie-pane rework (2026-08-13, cdc59ef1)

- Formation-energy plot now draws **only the lowest-energy envelope** for the selected growth
  condition, with open-circle kinks at the transition levels. The faint per-charge dotted context
  lines were removed — they read as clutter, not information.
- The modal collapses to **two columns** when a defect has no corrected charged states, so the
  transition-level panel never leaves an empty third column. The Sigma scroll box is sized at run
  time so its bottom edge lands on the same horizontal line as the middle column (page `zoom` is
  divided out, because `getBoundingClientRect` is zoom-scaled while style pixels are not).
- The relaxation-movie modal renders **one full-size perspective pane** instead of a four-view grid.
  MatterViz auto-fits its default camera, so the cell is centred and never cropped, its own controls
  stay reachable, and playback mounts one WebGL context per frame instead of four — which is what
  made frame stepping stall. Frames still double-buffer with a 180 ms retirement so nothing flashes.
- Defect-species highlighting is now passed explicitly to `renderGrid`, not inferred from the pane's
  element id, and the heading only claims "defect species in black" when a species is actually
  highlighted. For defects built purely from host species the note says plainly that colouring by
  element would repaint every atom of that element rather than the one defect site.

## Eagle tree flattened (2026-08-13)

`DFT/` on Eagle is no longer a symlink farm — every run directory was moved into it, so it is the
real tree with zero symlinks. `00_master`, which held 148 **empty** family-named folders, is gone.
A full OSZICAR walk found 1,348 run directories the farm builder had never indexed, including the
`Cu2Ca0.5Cd0.5SnS4` **HSE** defect ladder, now filed under `DFT/defect/HSE/`. Full detail in
`/eagle/wbg_defects/chalcogenide_defects/README.md`.

### Mistakes & corrections log

- **2026-08-13 — a silent ssh success that did nothing.** I ran the Eagle migration as
  `ssh polaris 'python3 -' < script`, saw exit code 0 with empty output, and moved on → WRONG: the
  Polaris login node had hit `fork: retry: Resource temporarily unavailable` and the interpreter
  never ran; the tree was untouched while I believed 106 directories had moved → THE GUARD: after any
  remote mutation, re-list the target and compare counts; never accept an empty stdout as success →
  GUARD LIVES IN the Eagle README ("Trap recorded") and the staged-script-plus-`nohup`-log pattern
  now used for every Eagle migration.
- **2026-08-13 — OSZICAR regex missed `F= -.169E+04`.** My fresh sweep of the Cu2Ca0.5Cd0.5SnS4
  campaign reported 0 defects because `-?\d+\.\d+` does not match VASP's leading-dot float →
  THE GUARD: parse the token after `F=` with `float()` instead of a numeric regex → GUARD LIVES IN
  `cu2cacd_sweep.py`'s `final_F`.

## Eagle tree rebuilt to the requested scheme + full inventory (2026-08-14)

The DFT archive on Eagle is now exactly `bulk/<theory>/<compound>` and
`defect/<theory>/<host>/<defect>/<charge>`. No symlinks, no `chempot/` kind, no campaign or
supercell level, no scripts/slurm/CSV/JSON inside the tree (303,105 such files deleted; 1,654,365
VASP data files untouched). `00_master` — 148 **empty** family-named folders — is gone.

Measured on disk, never from a CSV:

| | unique | runs | converged | size |
|---|---|---|---|---|
| bulk (8,564 compounds; polymorphs separate) | 8,564 | 35,326 | 35,053 (99.2 %) | 6.44 TB |
| defect (533 hosts) | 4,594 (host, defect) pairs | 57,404 | 56,410 (98.3 %) | 5.96 TB |
| **total** | | **92,730** | **91,463 (98.6 %)** | **12.11 TB** |

Per theory — bulk: PBEsol 7,356 / HSE+SOC 6,997 / HSE 6,992 / PBE 196 compounds.
Defect hosts: PBEsol 513 / PBE 12 / HSE+SOC 7 / HSE 1, with 2,999 / 1,198 / 366 / 31 unique
(host, defect) pairs respectively.

Two Globus transfers fed this: `a2bcx4-3x3x2-defects` (1.67 TB, 314 hosts) and `cdznx-pbe-series`
(624 GB, the CdSeS/CdZnTe/CdZnSe series — 63 alloy bulks plus 9,544 defect entries).

### Mistakes & corrections log

- **2026-08-14 — I flagged a quota emergency that did not exist.** I warned that 2.29 TB of new data
  might blow a 5 TB shared Eagle quota → WRONG: `myquota` reports `wbg_defects 35.32T / 100T`. The
  5 TB soft / 5.5 TB hard figure in my `alcf-polaris-access` skill file is stale → THE GUARD: read
  the live `myquota` before making any capacity claim, never quote a cap from a skill file →
  GUARD LIVES IN the Eagle README's quota section, which now records the real numbers and says to
  correct the skill file.
- **2026-08-14 — I parked 34,728 real bulk runs as "duplicates".** The target for
  `bulk/<th>/<comp>/<variant>/<alias>` is `bulk/<th>/<comp>`, which is the source's own ancestor;
  testing `os.path.exists(target)` was therefore always true and every run was treated as a
  duplicate → THE GUARD: when a target is an ancestor of the source, promote via a temp sibling
  (move out, delete the empty shell, move in) and count runs before and after → GUARD LIVES IN
  `eagle_restore_bulk.py` and the Eagle README's trap list.
- **2026-08-14 — I collapsed 20 distinct SQS configurations of every Cd-Zn-X defect onto one path.**
  Stripping the trailing `-N` from `defect-…_As_Cd_C1_Te2.82Cd4.41_0-13` looked like removing an
  index; it removed the configuration identity and parked 19 of every 20 runs → THE GUARD: never
  strip a suffix to make a name match a rule — carry it into the level name (`As_Cd-13`), and the
  same rule protects `_kesterite`/`_stannite`, where stripping would have merged 222 hosts into 111
  → GUARD LIVES IN `eagle_fixup_dups.py` and the Eagle README.
- **2026-08-14 — piped Python on Polaris buffers stdout, and I read the silence as a hang.** I killed
  working jobs and, worse, once read an empty stdout as a successful migration that had done nothing
  → THE GUARD: `ssh polaris python3 -u -`, and always re-list the target to confirm the mutation →
  GUARD LIVES IN the Eagle README's trap list.

## Defect tree normalised; raw physics extraction (2026-08-14)

`DFT/defect/<theory>/<host>/<defect>/<charge>` is now enforced and verified across **57,243 runs**.
The blocker was an undecoded dopant naming family: `M_<site>-<element>[-<config>]`, where `M` is a
placeholder and the dopant is the element after the dash. 7,913 directories were renamed
(`M_A-Ag-3` → `Ag_A-3`, `M_i_neut-Ag-10` → `Ag_i_neut-10`). Wrapper levels were collapsed, 19
host-bulk runs were moved out of the defect tree (all proven duplicates of runs already in `bulk/`),
227 dopant/native name collisions merged, 164 empty charge dirs pruned, and 21,241 A2BCX4 stage
siblings merged into 7,362 compounds.

`01_raw_dft/` (0 runs; a Python virtualenv) and `02_derived/` (5,675 runs, every one verified
already present in `DFT/`) were deleted. 303,105 script/slurm/CSV/JSON files were removed from
inside the tree; 1,654,365 VASP data files kept.

Two different meanings share the `-N` suffix and must not be conflated: A2BCX4/ABX2 PBEsol `-1/-2/-3`
are **relaxation stages** (constant cell in 161 of 200 sampled, F falling a few meV/atom), while
Cd-Zn-X `<ordering>-<rep>` are **SQS orderings** (identical 64-atom cell, 0.9–4.9 meV/atom spread,
non-monotonic). The site therefore publishes one row per composition: configurational average with
the spread as an uncertainty, and the ground-state ordering for the hull.

Everything published is recomputed from raw VASP output — OSZICAR `F` (never `E0`), EIGENVAL band
edges by occupancy, CONTCAR lattice/composition, KPOINTS, POTCAR TITELs, vasprun ε(ω),
ABSORPTION.dat α(E), DOSCAR element-projected DOS. Defect cells read only OSZICAR/CONTCAR/KPOINTS;
their band edges come from the host.

### Mistakes & corrections log

- **2026-08-14 — I claimed the library had almost no dielectric data and proposed running new DFT.**
  I reported "only 114 compounds have ε" and asked whether to launch thousands of LEPSILON jobs →
  WRONG: the number came from a **117-run test shard** of HSE+SOC plus the one tree (PBEsol) that
  genuinely has no optics; I had never extracted the HSE+SOC bulk tree at all. The real coverage is
  **6,235 of 6,998 HSE+SOC runs with ABSORPTION.dat and 6,760 with WAVEDER** → THE GUARD: never
  quote coverage from a shard — extract the tree, then count, and state the denominator alongside
  the numerator → GUARD LIVES IN the Eagle README's optics-coverage table.
- **2026-08-14 — I asserted a 1,026 eV energy spread meant "different cell sizes" without measuring.**
  The user challenged it and he was right to: across 200 compounds, **161 have identical atom counts
  at every stage** and the spread is a few meV/atom; only 39 mix cells, and there F/atom agrees to
  3 meV → THE GUARD: never explain an energy difference without dividing by atom count first →
  GUARD LIVES IN the Eagle README's `-N` section.

## Defect naming normalised; missing datasets located (2026-08-14, evening)

Every `A`/`B` site label is now the real host element, resolved from each defect cell's own
stoichiometry rather than by assuming A means cation: `Ag_A → Ag_Cd`, `Al_B → Al_Se`,
`As_i_A → As_i_Cd`, `M_A-Ag-3 → Ag_Cd-3`. 7,285 renames; zero raw tags remain. Compound duplicates
merged (`Te3As2 → As2Te3`, `CdTe0.75Se0.25 → CdSe0.25Te0.75`).

The `-N` defect configs were checked before any merge and are **distinct sites, not snapshots**:
`CdTe/Ag_i` spans 418 meV across 8 configs with nearest-neighbour distances 2.777–2.955 Å. The site
publishes one row per (host, defect) using the ground-state config, with the count and spread shown.

Datasets that appeared missing are tarballs in `/anvil/projects/x-mat250008`: In2O3 (42 GB),
ZnIn2X4 (23 GB), the full Cd-Zn-X source (4.1 TB) and 34 ZB semiconductors (48 GB). In2O3 and
ZnIn2X4 are transferring to Eagle. The HSE CdSeTe/CdZnTe defects are not on Eagle at all; their
processed results live in `/scratch/gautschi/rahma103/hse_master_data` as per-charge CSVs that carry
Structure/Energy/Forces/Stress but **no DOS**, so the raw DFT must come out of the tars.

Optics coverage corrected: **6,877 records over 6,763 unique compounds** carry a dielectric constant
(2,753 kesterite + 4,010 stannite) and are SLME-ready.

### Mistakes & corrections log

- **2026-08-14 — I collapsed three distinct interstitial sites into one name.** Mapping `X_i_A`,
  `X_i_B` and `X_i_neut` all onto `X_i` to tidy the names merged physically different defects across
  53 groups / 124 directories → THE GUARD: never drop a site or configuration tag to make a name fit
  a rule; resolve it to something meaningful (`X_i_Cd`) or keep it verbatim. Recovery was only
  possible because the raw extraction ran BEFORE the rename and recorded every original path and
  energy → GUARD LIVES IN `repair_interstitials.py` and the Eagle README ("extract before you
  rename").
- **2026-08-14 — my chem-pot vertex enumeration was computationally impossible.** Enumerating
  C(m, k−1) constraint combinations hung the full build on 5-element hosts with hundreds of
  competing phases → THE GUARD: reduce to hull-relevant phases first (one per composition, most
  negative ΔH, capped) and record how many were dropped per host → GUARD LIVES IN
  `build_chempot.py`.

## HSE Cd-Zn-X defects located; derived physics built (2026-08-14, deadline run)

**The HSE Cd-Zn-X defects were found.** They are inside
`/anvil/projects/x-mat250008/pccp_defectff_paper/Cd-Zn-X.tar` (4.1 TB) under `Cd-Zn-X/HSE/data/`,
as `defect-<host>-M_<site>-<element>-<config>/{Neutral,Charged±1,Charged±2}/` —
**39,147 HSE OSZICARs**. The naming matches the PBE set already normalised, so the same parser and
the `M_<site>-<El>` → `<El>_<site>` rename apply. Selective extraction is running.
The processed CSVs at `/scratch/gautschi/rahma103/hse_master_data` carry
Structure/Energy/Forces/Stress but no DOS, which is why the raw tree is required.

**Derived from raw only** (`build_all.py`, one build, no hand-patching, no CSV reuse):
28,218 bulk rows — 26,201 formation energies, 26,313 gaps, 6,764 dielectric constants,
6,764 absorption spectra, 22,784 decomposition energies with the phases they decompose to;
2,875 defect rows with Ef(q, E_F) at every named chem-pot vertex plus transition levels.
Determinism gate `derived_bulk sha256 = 250a55c1d6caaab8`.

Feeding it: phys_bulk 43,262 · phys_defect 56,257 · dos 40,007 · **steps 88,194** runs carrying
per-ionic-step energy, max force and its atom index, the INCAR VASP actually used, PAW TITELs and
the k-mesh.

### Mistakes & corrections log

- **2026-08-14 — an O(n²) build hung silently behind a pipe.** The first decomposition-energy pass
  scanned all 28k phases for every compound and emitted nothing for 30 minutes; `ssh … | tail`
  buffered the output so it looked identical to a hang → THE GUARD: index by element set for
  subset lookups instead of scanning, and always write a long job's stdout to a file on the cluster
  rather than piping it through `tail` → GUARD LIVES IN `build_all.py` (the `PH` phase index) and
  the Eagle README trap list.


---

# HANDOFF STATE — 2026-08-14 23:40 UTC

Read this section first. It is the current truth; everything above is history.

## Where the data is

```
/eagle/wbg_defects/chalcogenide_defects/
  DFT/bulk/<theory>/<compound>[/<variant>]/          variant = SQS ordering or relaxation stage
  DFT/defect/<theory>/<host>/<defect>/<charge>/
  log/                     extractors, derived products, build logs
  incoming/                In2O3 + ZnIn2X4 landing here from Globus
  duplicates_across_campaigns/  unclassified/  quarantine_non_physics/  defect_name_collisions/
```

theory ∈ {PBE, PBEsol, HSE, HSE+SOC} · charge ∈ {Neutral, Charged±1, Charged±2, Charged+3}

## Derived products (all from raw VASP, no CSV ever read)

`log/build_all.py` is the ONE build. `log/build_all.log` is its last run.

| product | file | count |
|---|---|---|
| bulk rows | `derived_bulk.json` | **28,218** |
| ├ formation energy / atom | | 26,201 |
| ├ band gap (occupancy-based) | | 26,313 |
| ├ ε xx/yy/zz + average | | 6,764 |
| ├ absorption α(E) | | 6,764 |
| └ decomposition energy + decomposition products | | 22,784 |
| defect rows | `derived_defect.json` | **4,020** |
| └ with chem-pot vertices | | 820 |
| chem-pot polytope vertices | `chempot.json` | per host, facet-named |

Determinism gate: `derived_bulk sha256 = 250a55c1d6caaab8`. A rebuild must reproduce it.

Raw extraction feeding it: `phys_bulk` 43,262 · `phys_defect` 56,257 · `dos_*` 40,007 ·
`steps_*` **88,194** (per-ionic-step E, max force + its atom index, full INCAR, PAW TITELs, k-mesh).

## Host matching — READ THIS BEFORE TRUSTING ANY "MISSING HOST" COUNT

A defect host and its bulk compound are the same material written differently:

```
defect  Ag1Al0.5In0.5S1Se1         bulk  Ag1Al0.5In0.5S1Se1_kesterite     polymorph suffix
defect  CdSe0.2Te0.8               bulk  CdSe0.20Te0.80                   decimal spelling
defect  Ag1Al0.5Ga0.5S2_kesterite  bulk  Ag1Al0.5Ga0.5S2_kesterite-3      stale stage suffix
```

Matching on the literal string reported **1,662 "missing hosts"**. Matching on **composition**
(preferring same polymorph, then lowest energy per atom) gives **444** — and defect rows went
2,875 → **4,020**. The remaining 444 are a real gap, dominated by `PBE/CdS` (404 groups) and
`PBE/ZnS` (40): those binary hosts have defect calculations but no bulk run in the same theory.

## HSE Cd-Zn-X defects — FOUND, extraction in progress

`/anvil/projects/x-mat250008/pccp_defectff_paper/Cd-Zn-X.tar` (4.1 TB) →
`Cd-Zn-X/HSE/data/defect-<host>-M_<site>-<element>-<config>/{Neutral,Charged±1,±2}/` —
**39,147 HSE OSZICARs**, plus a duplicate copy under `Cd-Zn-X/backup/HSE/`. Same flat naming as the
PBE set, so the existing parser and the `M_<site>-<El>` → `<El>_<site>` rename apply unchanged.
Selective extraction is running on Anvil into `/anvil/scratch/x-mrahman2/cdznx_hse`
(WAVECAR/CHGCAR/CHG/PROCAR/vaspout excluded); next step is Globus → Eagle → file under
`DFT/defect/HSE/`.

Processed HSE results (no DOS, which is why the raw tree is needed):
`/scratch/gautschi/rahma103/hse_master_data/{Neutral,Charged±1,±2}/*.csv`, columns
`Structure, Energy, Forces, Stress, Directory, Frequency, CFE, Tag`.

Other datasets, all tarballs in `/anvil/projects/x-mat250008`:
In2O3 42 GB · ZnIn2X4 23 GB (both transferring) · Cd-Zn-X 4.1 TB · 34_ZB_Semiconductors 48 GB.

## EVERY MISTAKE MADE IN THIS SESSION

**Applied to the data, then reversed** (recoverable only because extraction ran BEFORE renaming):
1. Parked **34,728 real bulk runs** as duplicates — the computed target was the source's own
   ancestor, so `os.path.exists(target)` was always true.
2. Stripped the trailing `-N` from Cd-Zn-X names, collapsing ~20 SQS configurations per defect and
   parking **76,406** dirs; 35,744 restored.
3. Collapsed `X_i_A`, `X_i_B`, `X_i_neut` onto `X_i`, merging three distinct interstitial sites
   (53 groups, 124 dirs).
4. Canonicalised compound names per-tree instead of globally → bulk `CdSe0.20Te0.80` vs defect
   `CdSe0.2Te0.8`.

**False statements made to the user:**
5. A "5 TB quota emergency" — the real quota is 100 TB with 35 TB used.
6. "Only 114 compounds have ε", quoted from a 117-run test shard of the one tree without optics,
   with a proposal to run thousands of unnecessary LEPSILON jobs. Real number **6,764**.
7. "A 1,026 eV spread means different cell sizes" — asserted without dividing by atom count;
   161 of 200 sampled compounds have identical cells.
8. "1,662 defect groups have no host bulk" — string matching instead of composition matching.
   Real number **444**.

**Caught by dry-run before applying:**
9. A classifier scanning path tokens against a formula regex — `DFT`, `A2BCX4`, `ABX2`, `POSCAR`,
   `OUTCAR` and every single capital matched; a folder ending `_pbesol` flipped an HSE run's
   theory. Would have misfiled 65.8 % of defects.
10. A canonicaliser that alphabetised elements: `Cu2ZnSnS4` → `Cu2S4SnZn`, 20,895 dirs.
11. A "most explicit spelling wins" survivor rule that chose `Te3As2` over `As2Te3` and preferred
    the pipeline's own `_supercell` / `__from_defect_tree` suffixes.

**Engineering bugs (cost time, not correctness):**
12. Piped Python buffers on Polaris — empty stdout read as a hang, and once as a *successful*
    migration that had done nothing. Always `python3 -u`, always re-list the target.
13. `nohup … &` inside an ssh command is SIGHUP'd on session close; the log stays 0 bytes.
14. Shell `for` loops trip the login-node fork limit.
15. OSZICAR regex missed VASP's `F= -.169E+04` form → 0 defects reported for a 302-run campaign.
16. EIGENVAL occupancy convention wrong for ISPIN=2 → every gap came out empty.
17. `read_outcar` slurped whole multi-GB OUTCARs → extraction stalled.
18. O(n²) decomposition scan and C(m, k−1) vertex enumeration — both simply hung.

**The pattern:** failures cluster in *inferring meaning from names* — site tags, configuration
indices, polymorph suffixes, decimal spellings — where tidiness was chosen over fidelity and a real
distinction was destroyed. The guard that has worked every time: dry-run first, verify against the
physics (atom counts, energies, geometries), and keep an extraction snapshot taken **before** any
rename so mistakes stay reversible.

## What is still open

- Charged defect states are **uncorrected**. LOCPOT exists for HSE / HSE+SOC / PBEsol defects
  (FNV possible) but NOT for the 41,725 PBE Cd-Zn-X runs (image-charge only). No OUTCAR carries the
  site-potential block eFNV would need.
- SLME itself is not yet computed — the ingredients (gap, direct/indirect, ε, α(E)) are all in
  `derived_bulk.json`, but no AM1.5G reference spectrum was found on Eagle or Anvil. It must be
  supplied or generated before SLME can be published.
- 444 defect groups have no same-theory bulk host; 284 have no neutral run. Both excluded and
  counted, never filled.
- Site payloads have NOT been rebuilt or deployed from these derived products yet.
- `x-mat230068_2026-05-26.tar` (5.4 TB) index still running.

---

## 2026-08-15 00:20 UTC — datasets landed, payload builder written, chem-pot gap found

### In2O3 and ZnIn2X4 are on Eagle

All four Globus tasks report SUCCEEDED (`--notify off`, as always):

| label | task | bytes |
|---|---|---|
| `in2o3-to-eagle` | `9d492101` | 42,226,558,540 |
| `znin2x4-1` | `9fc23b90` | 3,649,951,714 |
| `znin2x4-2` | `a2200621` | 2,650,953 |
| `znin2x4-3` | `a4235a4a` | 19,331,610,798 |

They are in `incoming/` and extracting into `incoming/x/` with `WAVECAR*`, `CHGCAR*`, `CHG`,
`PROCAR*`, `vaspout*`, `POT*` and `WAVEDER*` excluded. Eagle is at 34 TB of a **100 TB** quota, so
space is not a constraint (an earlier "5 TB emergency" in this log was wrong).

Layouts, read off the archives rather than assumed:

```
In2O3/pbesol/defect_calcs_pbesol/<defect>_<site>_<charge>/Rattled/{OSZICAR,OUTCAR,DOSCAR.gz,LOCPOT.gz,…}
ZnIn2X4_Project_1/Ultrathin_ZnIn2Te4/reference_compound/<phase>/
ZnIn2X4_Project_2/c_c_coupling_on_ultrathin_ZnIn2X4/<system>/<state>/
ZnIn2X4_Project_3/HSE_Reference_Energy/<phase>/
```

Two things to carry into the extractor: In2O3 writes `DOSCAR.gz` / `LOCPOT.gz` / `POT.gz`, so the
readers must accept a gzipped variant; and its charge state is baked into the directory name
(`O_i_C2_-2`) rather than a `Charged-2` level.

### The defect chem-pot gap — cause found

Only **820 of 4,020** defect rows carried a formation energy, and the reason was not the physics:
`chempot.json` had been built for **PBE only** (110 hosts, 40 with a solvable polytope, 196 phases).
Every PBEsol, HSE and HSE+SOC defect therefore fell through to "no chem-pot vertex" and could only
report a raw ΔE. `build_chempot.py` is now running over all four theories; the PBE-only file is kept
as `chempot_PBE_only.json` so the before/after is checkable.

**Guard:** a coverage number is only meaningful next to the input it was computed from. Print the
per-theory host and vertex counts at the end of every chem-pot build, and read them before quoting
any defect-Ef coverage.

### `build_payload.py` — the site payload, from the derived products only

`log/build_payload.py` reads `derived_bulk.json`, `derived_defect.json`, `chempot.json`,
`dos_*.jsonl` and `steps_*.jsonl`, and writes `log/payload/`:

| output | content |
|---|---|
| `data.json` | compounds, defects, elemental references, and the struct/dos/run key lists |
| `dos/<key>.json.gz` | element-projected DOS, Fermi-shifted |
| `runs/<key>.json.gz` | INCAR, PAW TITELs, k-mesh, EDIFFG, and per-ionic-step E, ΔE, Fmax + its atom |
| `optics.json.gz` | ε tensor and α(E) per key |
| `chempot.json.gz` | the polytope vertices, per theory and host |

Two rules it enforces:

- **One row per (theory, compound, polymorph), at the ground state.** The `-N` suffix
  (`stannite-12`, `kesterite-3`) is a separate SQS ordering or relaxation stage of the same
  material, so the lowest F/atom member is published and the configuration count plus the spread in
  meV/atom ride along as provenance. Nothing is averaged.
- **The run is matched to the compound by energy, not by position.** `derived_bulk.json` carries no
  path, so where a compound has several variant directories the builder picks the one whose total
  energy matches the published ground state. Taking the first would pair a compound's numbers with
  a different run's INCAR and k-mesh — silently.

The compound row keeps the 19 fields the shipped template already indexes and appends four:
`[19] decomposes_to`, `[20] configurations merged`, `[21] spread meV/atom`, `[22] PAW potentials`.
The template guards every high index with a `v.length>N` test, so appending is safe.

Defect rows gain `vx` (Ef per named chem-pot vertex per charge), `tl` (transition levels), `dn`
(the atoms added and removed), `nc`/`sp` (configurations and spread), and `corr`, which currently
reads `uncorrected` on every charged state and must keep reading that until FNV is applied.

### Status of the long-running jobs

| job | where | progress |
|---|---|---|
| In2O3 + ZnIn2X4 extraction | Eagle | 35 GB, running |
| HSE Cd-Zn-X extraction | Anvil `/anvil/scratch/x-mrahman2/cdznx_hse` | 166 GB, 13,227 of 39,147 OSZICARs |
| chem-pot, all four theories | Eagle | running |
| payload build | Eagle | 28,218 bulk rows read, dos/ and runs/ writing |

Small-file writes on Lustre run about 600 files/minute, so the 28k + 28k dos/runs pair takes the
better part of an hour. Tar the payload directory before moving it rather than copying file by file.

---

## 2026-08-15 01:40 UTC — defect-Ef benchmark against the validated CSV: three real errors found

Protocol source: `kosmos/skills/dft-defects.md` §L1 (assembly), §J (finite-size correction),
§E (chemical potentials) and `kosmos/skills/chempot-to-partial-pressure.md`, all read in full.

```
E_f[X^q](E_F) = E_tot[X^q] - E_tot[pristine, SAME cell and settings]
              + Sum_i n_i mu_i           (n_i = atoms REMOVED; added -> n_i < 0)
              + q (E_VBM + E_F)
              + E_corr(q)                E_corr = E_lattice(q) - q dV_align
```

The benchmark is `cdsete_defect_library_generation_pbesol.csv` — the campaign's own validated
table, carrying `Toten_pure`, `Toten_{p2,p1,neut,m1,m2}`, `Corr_*`, `VBM`, `gap` and the summed
chemical-potential term at the Cd-rich and Te-rich limits. Reproducing it from raw is the gate.

### Finding 1 — the pristine reference was the wrong run, worth 0.84 eV on every CdTe defect

PBEsol CdTe has two 216-atom pristine runs, and they are not interchangeable:

| run | a (Å) | F (eV) | ISIF | k-points |
|---|---|---|---|---|
| `DFT/bulk/PBEsol/CdTe/216_atoms` | 19.497632 | **−592.11621** | 3 (vc-relax) | KSPACING 0.030 |
| `DFT/bulk/PBEsol/CdTe` | 19.499945 | **−592.95479** | 3 | — |
| every defect cell | **19.4999** | — | **2** (fixed cell) | **Γ-only** (ShakeNBreak) |

Gate 2 requires the reference to share the defect cells' lattice, and L1 requires the same
settings, so the reference is the **19.4999 Å** run at **−592.95479**. Taking the vc-relaxed
216-atom run instead shifts every CdTe defect formation energy by **0.84 eV** — larger than most
of the formation energies themselves.

**Unresolved and stated as such:** the CSV's `Toten_pure = −592.22` matches **neither**. A sweep of
every Cd108Te108 run in the tree (15 of them, all four theories) finds nothing at −592.22; the
nearest PBEsol value is the `V_Te+Te_i` Frenkel pair at −592.19138, which has pristine
composition but is not pristine. The CSV's reference run is not in this tree.

### Finding 2 — 15 antisite directories were labelled backwards

`Cd_Te` held a cell of **Cd107 Te109** — that is Te sitting on a Cd site, i.e. `Te_Cd`. Confirmed
three independent ways before anything was renamed:

- **composition** vs the cell-matched pristine (Cd108 Te108) → dn = {Cd −1, Te +1}
- **NELECT** from the run's own OUTCAR against the PAW ZVALs → 1938 = 1944 − 12 + 6, the same swap
- **the CSV** → its `Cd_Te` neutral is −587.25, which is the energy in the directory named `Te_Cd`
  (−587.24137); its `Cl_Te` −591.06 matches `Cl_Te` −591.05638, so the convention is the CSV's

Affected: PBEsol CdTe, CdSe0.25Te0.75, CdSe0.5Te0.5, CdSe0.75Te0.25 and HSE+SOC CdSe0.25Te0.75.
**14 swapped**, and one pair collided because two directories held the same defect — that one is
now `Cd_Se-2`, a second configuration, not a deletion. Zero `__swaptmp` left in the tree.

A wrong antisite label is not cosmetic: it inverts the sign of dn, so `Sum n_i mu_i` is wrong by
`mu_Cd − mu_Te`, which at the Cd-rich vertex of CdTe is the full width of the stability window.

### Finding 3 — eFNV IS possible; the earlier "no site potentials anywhere" note was wrong

The defect INCARs carry `ICORELEVEL = 0` **specifically** for the Kumagai-Oba correction
(the comment in the file says so), and the OUTCARs do contain the block:

```
 average (electrostatic) potential at core
  the test charge radii are     1.0698  1.1897  0.9406
       1 -39.0982       2 -39.0417       3 -39.3071   ...
```

So the anisotropic eFNV scheme — which takes the ε **tensor** rather than a scalar and derives its
alignment from the model charge instead of an eyeballed plateau — is available for this campaign,
not just Makov-Payne. Per §J3 the plan is MP for continuity **and** eFNV in parallel, with any
(defect, q) whose two schemes differ by more than 0.1 eV flagged provisional rather than quoted.

### Energy cross-check — raw extraction reproduces the validated table

| defect | raw (this pipeline) | CSV | Δ |
|---|---|---|---|
| `Cl_Te` neutral | −591.05638 | −591.06 | 0.004 |
| `Cd_Te` neutral (post-fix) | −587.24137 | −587.25 | 0.009 |
| `As_Te` neutral | −592.38232 | −592.40 | 0.018 |
| `Cd_i` neutral | −592.38436 | −592.40 | 0.016 |
| CdTe VBM | 2.140077 | 2.14 | 0.000 |
| CdTe gap | 0.633557 | 0.64 | 0.006 |

VBM and gap land exactly; the energies scatter by ≤0.02 eV, consistent with the CSV quoting a
slightly different relaxation snapshot at 2 dp. No systematic offset.

### Guards added

- **Never take the pristine reference by name.** Match it by LATTICE against the defect cells and
  by settings (k-mesh, ENCUT, POTCAR); for CdTe the name-matched choice is 0.84 eV wrong.
- **Never trust a defect label.** Derive dn from the cell's composition against the cell-matched
  pristine, and cross-check it against NELECT through the PAW ZVALs. The directory name is
  provenance, not physics.
- **Do not infer the pristine composition from the modal composition across defects.** Most of a
  host's defects sit on the anion site, so the mode reports the anion one short and every label
  then reads as shifted — that produced a bogus 30-of-79 mismatch on CdTe before it was caught.

### Chemical potentials and the P–T growth window

`chempot.json` covered PBE only (110 hosts, 40 with a polytope), which is why only 820 of 4,020
defect rows had a formation energy. Per-theory builds are running for PBEsol, HSE and HSE+SOC;
PBE re-ran clean with `sha256=b0ce59b6e5e9a744`.

For the Kosmos-style (T, p) growth-window contour, the skill bundles Shomate blocks for **N₂, O₂,
H₂ and F₂ only** and states explicitly that an unbundled gas must KeyError rather than be guessed.
Chalcogenides need **S₂, Se₂ and Te₂**, so those blocks have to be pulled from NIST-JANAF and
verified against the printed S°(298.15) before any contour is drawn — a recalled coefficient set
is exactly the failure the skill's gate exists to catch.
