
## 2026-08-17 — bulk breakdown restored, SLME, per-vertex equations, all-rows site marks, Eagle is the build home

User reports fixed and live-verified 10/10 (build 00913f6b8f69):
1. **"Entire bulk broken"** — the Gautschi-era payload only ever emitted v[0..22]; the panel's
   decomposition term-by-term (v[27]), ionic-steps/calculation-type filters (v[28-30]) and SLME
   (v[4]/v[14]) had been silently dark since the payload moved off the original bundle. decomp()
   in build_all now STORES its winning hull mix; the builder emits the full 31-column row.
   Calculation-type and steps dropdowns are populated again (5/6 options).
2. **SLME implemented from the campaign's own α(E)** (Yu–Zunger, L=500 nm, T=300 K, AM1.5G from
   the ASTM G173-03 table, provenance/astmg173.csv). First attempt published 2–6% for 30%-class
   materials: the DFT spectra carry smeared SUB-GAP tails and the blackbody flux diverges at low
   E, so J0 exploded — SLME uses the band gap as absorption onset. Distribution now 0–32.9%,
   median 18%. Radiative-only (Δ=0) is stated on the panel — the direct-allowed gap was never
   archived. 3,521 row-orderings carry SLME.
3. **ε sanitized** — any dielectric run with a component ≤0 or >1000 publishes nothing.
4. **Chem-pot dropdown for charge-resolved DOS** — the onchange handler rebuilt its own option
   list with the first entry re-selected before reading the pick; it could never switch. Fixed.
5. **Per-vertex derivation block** — every solved vertex now shows: elemental references μ⁰,
   Δμ ≤ 0, the host equality with ΔH_f, each bounding-phase equality with its ΔH_f (evaluated
   from the vertex μ so every equation closes exactly), the solved μ, then Σnᵢμᵢ.
6. **Defect-site marks for ALL rows, precomputed data-side** (log/gen_marks.py, numpy): 2,371
   host-diff (incl. replicated-primitive supercells — Cd_i in CdSe now marks its black site),
   251 foreign-element fallback, 1,672 no-geometry (honest reason stored), 65 unmarkable.
   Shipped in the payload (r.mk/r.vc); the client only recomputes when the payload is silent.
7. The 100+-row competing-phase energy dump is gone from the defect panels (replaced by the
   derivation block + a one-line count). GLM's 732-row relabel pass is wired into build_all
   (log/defect_relabels.json) so rebuilds keep corrected names; audit_dn now reports
   label==cell on 4,216/4,363 rows (4 held mismatches, 2 unparseable, 141 non-commensurate).
   Numbered variants display as "(site N)"; relabelled rows show "archived as <old name>".

**DFT campaigns running on Gautschi (the ONLY thing left there):**
- Bulk PDOS fill: 1,897 HSE06 static+LORBIT=11 runs (pdos_runs), arrays 15310281/15310284/15310285.
- Defect PDOS fill (PBEsol): 4,995 charge-state statics (ddos_runs) covering the 1,142 PBEsol
  rows without DOS. All arrays resubmit-safe (DOSCAR guard). Both queues were blocked on
  MaxCpuPerAccount at submit time (the account's chg_g arrays); standby will drain them.
  Batch scripts need "#!/bin/bash -l" on Gautschi or module is not found — fixed in place.
- Harvest after completion: dos_vasprun-style extraction → dos_defect jsonls → site_build.sh.

**Eagle is the canonical build home (user directive).** site/repo is a full clone; identity
msehabibur, token in ~/.git-credentials (mode 600, user home). ONE command builds and ships:
  bash /eagle/wbg_defects/materialsHUB/telluride/log/site_build.sh
(= build_all → audit_dn → gen_marks → build_payload_eagle → assemble docs incl. fresh dos
extraction + mark merge + listing-derived key lists → build_site → commit+push as msehabibur).
Big dos_defect jsonls are split to ≤150 MB parts before parsing (login-node OOM guard).
Gautschi mhub_build is deleted once the first Eagle-built push is verified live.


## 2026-08-17 (later) — decomposition switched to the stoichiometric BINARY channel
User: "I only want binary phases the way we defined in the nanoHUB tool" (ChalcoDB), plus the
configurational-entropy term-by-term. The old client recomputed from an incomplete binary table
(the acknowledged ChalcoDB-era mistake, -4.12 vs the true -0.29); the builder now solves the
exact stoichiometric binary combination per compound with a dense two-phase simplex over the
FULL same-theory binary set (+ elements at dH=0), and adds ideal-mixing entropy
kBT(298.15 K)*sum_sublattice n*sum f ln f from the formula's fractional sublattices.
Published v[1] IS this number; v[27] carries the terms incl. per-sublattice S breakdown;
v[19] lists the binaries; v[9] = S. Validated: Cu2ZnSnS4 -> Cu2S+ZnS+SnS2 (d=-0.483);
CdSe0.25Te0.75 -> 0.75 CdTe + 0.25 CdSe, S=-0.0144; K0.5Rb0.5AlS2 -> 0.25 K2S+0.25 Rb2S+
0.5 Al2S3, S=-0.0178. 19,880/19,880 decomposable row-orderings on the binary channel, zero
fallbacks. NOTE the subset-enumeration first attempt ran >54 min and was replaced by the LP.


## 2026-08-17 (final, shipped 1b351d791, live 8b3728ed0f64, verified 10/10)
- Binary-decomposition build is LIVE and verified 10/10 reloads: CZTS shows Cu2S+ZnS+SnS2 with
  d=-0.4832 on screen, K0.5Rb0.5AlS2 shows the -0.0178 eV cation-site entropy breakdown, zero
  console errors, published column == derived breakdown on every row.
- DFT status (Gautschi, sole remaining role = running DFT): ZERO runs completed yet -- everything
  pends on the account's 48-CPU high-priority cap (other amannodi members, bsamanta alone 171
  running jobs). The three original bulk-PDOS arrays carried the pre-fix batch script (module:
  command not found -- Gautschi batch shells need '#!/bin/bash -l') and would have failed on
  start: cancelled, resubmitted as 15319753 (highmem 0-7), 15319754 (cpu 8-999%10), 15319755
  (cpu 1000-1896%10). Defect-DOS: 4,995 runs, POTCARs 4995/4995, arrays 15316536-40
  (cpu-standby %10, fixed script). Highmem QOS caps 8 submitted jobs/user: slots split 4 bulk +
  4 defect, and an scrontab feeder (hm_feed.sh, */20 min; needed explicit -A/-p/-q to be
  accepted) tops the quota up with the next unfinished defect runs; marker files + in-job DOSCAR
  guard make it double-submission- and rerun-safe. Truncated ddos_pkg.tgz from an interrupted
  scp was recopied and checksum-verified (d11246281c617194).
- Mistakes log (append, four parts): submitted arrays before fixing the batch-shell bug ->
  the module-not-found failure was ALREADY in the first 12 failed tasks when the later arrays
  were queued with the same script (his standing rule: a repeated mistake is worse than the
  original) -> THE GUARD: after any slurm-script fix, grep the submitted arrays' scripts
  (scontrol show job | Command) and cancel/resubmit any that predate the fix -> GUARD LIVES IN
  this README section + the resubmission pattern above.


## 2026-08-17 (night) — over-marked defect sites + rogue charge states (ZnTe HSE+SOC Vac_Te)
User: "Vac_Te in ZnTe HSE+SOC is a mess; a lot of cases show 3 defect sites even though it has 2".
Two distinct bugs, both fixed and shipped:
1. OVER-MARKING (504 rows): (a) the phantom-ring filter used 1.2 A but a relaxed substituent sits
   up to ~2 A off the vacated site -> ring AND marked atom drawn for one site; (b) vacancy rings
   were not capped by dn. gen_marks now uses 2.2 A (half a bond) and rings = NET missing atoms
   (rem - min(add,rem)); marks capped at dn's added atoms; the client filter was aligned the same
   way. Whole-library audit (marks+rings vs label parts): 2,527 exact, 59 "over" = rows whose CELL
   genuinely holds more sites than the label (mislabel family; marks show the truth), 39 under
   (partial geometry). Precompute rerun on Gautschi (numpy) from relayed trajs/structures.
   Marks now carry tk = the trajectory they index; the client uses them only when that exact
   file is displayed (an HSE row rendered from a PBEsol fallback or the unrelaxed model must not
   reuse indices computed on another structure).
2. ROGUE CHARGE STATES: ZnTe HSE+SOC Vac_Te published Ef@VBM 159.5 eV for q=-1/-2 -- those runs
   are +160/+165 eV off the neutral (different settings/reference); the settings gate checked the
   NEUTRAL only. New per-charge-state gate (|dE_q - dE_0| > 15 eV -> withheld with reason) in the
   payload builder now, and provenance/patch_build_all_qgate.py to apply the same in Eagle's
   build_all on resume. Only 2 rows in the library trip it (ZnTe Vac_Zn, Vac_Te, HSE+SOC).


## 2026-08-17 (late night) — DFT campaign status snapshot
- Completed: 1 / 4,995 defect-DOS statics (Ag1Al0.5Ga0.5Se2/Vac_Ag/Charged+1, PBEsol, converged
  in 1 ionic step, LORBIT=11 honoured, 2000-point per-ion DOSCAR = harvestable); 0 / 1,897 bulk
  HSE06 PDOS.
- Running: 3 more Vac_Ag charge states (cpu-standby, ~30-60 min each for 287-atom PBEsol
  statics) + the first 2 bulk HSE06 PDOS on highmem (multi-hour SCF each, 2x2x2 mesh).
- Pending: 9 defect + 3 bulk array slices, hm_feed scron alive; account cap (48 hp CPUs) held
  by another member's 172 running jobs -- everything advances as standby backfill only.
- Post-fix failure count: 0. (12 FAILED / 3 CANCELLED in accounting = the pre-login-shell-fix
  arrays, cancelled by me and resubmitted.)
- Harvest plan unchanged: dos_vasprun-style extraction of DOSCAR/vasprun -> dos_defect /
  dos_bulk jsonls in log/ -> site_build.sh on Eagle. Do not harvest until volume is meaningful.

### DFT status 2026-08-17 22:30 (Gautschi; ALCF still unreachable)
- Defect statics (`ddos_runs`, 4,995): **4 done** (Ag1Al0.5Ga0.5Se2 Vac_Ag q=+2/+1/−1/−2, 28–43 min each on 128 cores), 5 array slices pending on cpu-standby behind the account CPU cap (user's `chg_g` arrays, 40 pending).
- Bulk HSE06 PDOS (`pdos_runs`, 1,897): **4 done** (Ag2Ba0.5Zn0.5Ge1Se4, Ag2Ba0.5Cd0.5Ge1Te4, Ag2Ba0.5Cd0.5Zr1Se4, Ag2Ba0.5Cd0.5Sn1S4; 2.5–3.5 h each on highmem), 2 slices pending on cpu-standby.
- highmem feeder rewritten (`/scratch/gautschi/rahma103/hm_feed.sh`): the old scron copy sat PENDING on the same account cap and never fired; the partition rejects <96 cores and `highmem-qpart` allows 384 CPUs/user → feeder now keeps **4 × 96-core jobs** (alternating defect static / bulk PDOS) in highmem, breaks on sbatch failure (an infinite loop on a rejected sbatch was caught and fixed), runs from a login-node loop every 15 min (`login02`, pid 3383874) with the scron kept as backup. Both array scripts now use `mpirun -np ${SLURM_NTASKS:-128}`. First four highmem jobs submitted 22:28 (15331282–85). Log: `ddos_runs/logs/hm_feed.log`.
- Failure accounting today: 12 FAILED + 3 CANCELLED = pre-login-shell-fix `pdos_b` slices only; 0 post-fix failures. `mhf_leps_*` TIMEOUT/OOM jobs are the user's own dielectric runs, not the DOS campaign.

## 2026-08-18 — bulk energetics re-derived per run footing; the ±100/+2252 eV/f.u. decomposition energies were mixed-footing artefacts

**Report:** "some compound has decomp ~2000, some ~100, some −100". Whole-library machine audit
(`provenance/footing_audit.py`, run over every bulk run record) found three mechanisms, none of them
a formula problem:

1. **The theory label is a directory name; the INCAR is what ran.** 55 "PBEsol"-labelled runs are
   HSE (LHFCALC=.TRUE.), 39 "HSE" runs are plain PBEsol, and the HSE tree itself mixes HSE06 built on
   PBE (3,842 records, mostly ENCUT 400) with HSEsol built on PBEsol (5,827 records, ENCUT default) —
   total energies ~0.2 eV/atom apart. `build_all.py` took the lowest-energy variant per compound AND
   per element regardless of footing (PBEsol|CdTe's ground state was an 8-atom run at −3.258 eV/atom
   that matches no PBEsol record and is 3 meV from the HSEsol value; the CdSeTe alloys sat on a
   PBEsol footing and were compared with it → +85..+106 eV/f.u.).
2. **Diverged final SCF steps published as total energies:** Na2Sr1Sn1Te4 HSE kesterite F = +4437 eV
   (last step 372 eV/atom above the run's own minimum), Na2Cd1Sn1Se4 HSE kesterite −18.8 eV/atom,
   Na1Ag1Cd1Zr1Se4 HSE stannite −281.9 → −233.5 eV in one ionic step with 2.3 eV/Å forces.
3. **"Formula unit" = the literal name** (Cd108Se27Te81 = 216 atoms), so a 0.02 eV/atom number
   printed as 4 eV/f.u.

**Fix (payload builder `build_payload_gautschi.py` = repo `provenance/build_payload_eagle.py`, live
build e13c38ab1a17):**
- Every run record is classified from its INCAR into a footing class (functional, hybrid base, SOC,
  +U): PBE, PBEsol, HSE06 (PBE base), HSE06 (PBEsol base), HSE+SOC (PBEsol base), PBE+U.
- Elemental references are built per class **and per PAW potential** from the element run records
  (`EREF[class][Na_pv]`), min F/atom, diverged/positive runs excluded; the row's E_f uses the
  reference computed with the PAW the row's own POTCAR list names. Classes with references:
  HSE/PBE 86, HSE/PBEsol 21, HSE/PBEsol+SOC 49, PBE 86, PBEsol 87.
- A row's published energy is traced to a run record (|ΔF| < 0.02 eV): matched-ok 20,191; realigned
  28 (published F matches no same-class run → energetics from the archived same-class run, properties
  withheld when the two differ by > 0.1 eV/atom, e.g. PBEsol CdTe now from `216_atoms-2`, −0.379
  eV/atom); mislabelled 4 (Ca/Cu/Zn "HSE" and Zn "HSE+SOC" are PBEsol/HSEsol runs → withheld);
  diverged 7 (final step > 50 meV/atom above the run's minimum → withheld); no record 2.
- Decomposition = LP over every same-class binary + elements (nanoHUB rule), each binary's ΔH_f
  from its own record against the same-class references; the host's own composition is excluded;
  formula unit = name stoichiometry gcd-reduced when integral (Cd108Se27Te81 → Cd4SeTe3), fractional
  alloy names keep their unit so the k_BT Σ f ln f term is per the same f.u.
- Cross-check gate after the loop: E_f differing from the PBEsol value of the same compound+ordering
  by > 0.5 eV/atom (library median 0.064, p99 0.42 over 12,640 pairs) → withheld (75); an ordering
  > 0.3 eV/atom above the other still-valid ordering at the same theory → withheld (124).
- Payload: v[0] E_f, v[1] d, v[7] = footing label (REFS key), v[27] carries footing/refs/terms (each
  term names its archived run) or `withheld` + reason; refs gain one set per class. Template: uses
  `REFS[v[7]]`, shows the footing on the "Level of theory" line, a withheld-reason notebox, PAW +
  ENCUT per reference, gcd f.u.

**Result:** decomposition |d| ≥ 10 eV/f.u.: 1 → 5 (all physical: P2O5/As2O5/In2O3 −17..−10 = ΔH_f
per f.u. vs elements, TeN2Cl6 +11 with E_f +0.9); ≥ 3: 617 → 499; E_f coverage 20,017 / 20,232
rows, decomposition 19,712; 226 rows withheld with the reason on the panel. Independent recompute
(Cu2ZnSnS4 PBEsol kesterite from raw records: E_f −0.479, d −0.483) = published. Live 10/10 on the
ten named rows (Na2Sr1Sn1Te4/K2Ba1Ge1S2Te2/Na1Ag1Cd1Zr1Se4 HSE withheld with reasons; Cd108Se27Te81
PBEsol −0.41 / +0.09; CdTe PBEsol −0.38 / −0.76; Cs2SrZrTe4 +5.71 in both PBEsol and HSE+SOC).

**Must move upstream when ALCF is back:** `build_all.py` must (a) label theory from the INCAR, not
the directory, (b) pick the ground state and the elemental refs within one footing class and PAW,
(c) drop diverged final steps — the same rules now in `provenance/build_payload_eagle.py`. Until then
`chempot.json` mu0 for HSE (used by the defect side) is still the mixed-footing minimum; the defect
settings gate (|ΔE|/atom > 0.05 host vs defect) limits, but does not remove, that exposure.

### Mistakes & corrections log
**2026-08-18 — I published formation/decomposition energies without checking that every term was on
one footing.** WHAT I DID WRONG: took `Ef_per_atom`/`E_decomp` from `derived_bulk.json` and built the
binary LP over "same theory" rows, where "theory" was a directory label. WHY IT WAS WRONG (his
report): decomposition energies of ~2000, ~100 and −100 eV/f.u. on the live site — energies from HSE
runs, HSEsol runs, PBEsol runs and diverged SCFs were being subtracted from each other. THE GUARD:
`provenance/footing_audit.py` — classify every run from its INCAR, cross-tabulate against the label,
trace every published F to a record, and print the |Ef − Ef_PBEsol| distribution; a build ships
only if the audit's mislabelled/diverged/unmatched counts equal the withheld counts in the payload
log. WHERE THE GUARD NOW LIVES: `build_payload_eagle.py` (classify_row, EREF, cross-check gate,
"row footing modes" line) and this section.

## 2026-08-18 (later) — defect ladder gates: the crazy-negative formation energies and the neutral-only twin rows

**Reports:** the ZnTe HSE+SOC Vac_Zn table (Ef@VBM −2.27/−2.25/−2.11, +1/+2 already withheld);
"some defect formation energy is crazy negative"; "Al_i … ord 1 shows neutral it is wrong."

**Audit:** 63 vertex/charge entries published Ef@VBM < −0.5 (worst −3.64, Ag_i/Ge_i in
Ag2Ca1Ge1S4_stannite with dE −10.7/−16.2 eV; Al_i in K0.5Ag0.5Al1S1Te1 at +129 eV for every
charge). Three mechanisms: (1) the host reference is hpa × N with hpa from a small k-converged
cell while the supercell ran Γ-only — for ZnTe HSE+SOC the 215-atom Vac_Zn cell comes out MORE
bound per atom (−3.6862) than the perfect crystal (−3.6718), which is impossible, and 14 meV/atom
of k-mesh error is 3.1 eV in dE; (2) whole ladders consistently off (the +129 eV family passes a
per-charge gate); (3) μ0 from the mixed-footing chempot build (no true HSE+SOC Zn elemental run
exists). No pristine supercells exist in the archive (build_all skipped them), so the correct
E_bulk is not derivable on Gautschi.

**Fix (payload builder, live build e13c38ab1a17, commits db0ce7c17):** three whole-ladder gates —
neutral |dE|/atom > 0.05; pure-removal defect cell more bound per atom than the host (impossible);
neutral Ef@VBM < −0.2 at any solved vertex (host would decay spontaneously → broken chain). A
gated ladder keeps dE/DOS/structures and shows the exact reason on every charge row. Neutral
Ef@VBM < −0.2 now 0 (the 4 remaining < −0.5 entries are charged-state-only — legitimate E_F
pinning physics). Resolved rows 163 → 150.

**Twin rows:** 732 bare-host rows (e.g. `Ag1Al1Se2` + `Al_i`) carried only the neutral per-site
scan of a defect whose full charge ladder lives on the `_kesterite`/`_stannite` row — that is the
"shows only Neutral" complaint. Dropped when the suffixed twin exists and the bare row has no
charge state the twin lacks; verified 0 resolved bare rows had unresolved twins. Defects
4,363 → 3,631 rows; site-mark fields (mk/vc/mkwhy) grafted onto the new rows (1,749 carried).

**Live 10/10:** ZnTe Vac_Zn withheld with the more-bound-than-bulk reason on the panel; Al_i =
exactly one Ag1Al1Se2_kesterite row with q = −2…+2; control CdTe HSE+SOC Vac_Cd unchanged at
4.285476 eV; 0 negative neutral rows; defects 3,631.

**For Eagle build_all:** the real fixes are upstream — run/keep pristine supercells per host and
use them as E_bulk (never hpa × N across k-meshes), build mu0 per footing class, and emit the
three gates' inputs. Until then these payload gates stand.

## 2026-08-18 (later still) — Vac_Ba q=−2, the transition-level gate, and antisites drawing two sites

**"Vac_Ba in Cu1.5Ag0.5BaSnS4 ord 2 is negative why":** the arithmetic was consistent but the q=−2
run itself is broken — dE(−1→−2) = 2.18 eV where each added electron must cost ≥ E_VBM = 4.95 eV,
so the implied (−1/−2) acceptor level sits 2.77 eV BELOW the VBM (impossible); it passed the crude
15 eV gate and published Ef@VBM = −1.24/−1.69. New vertex-independent gate on every charged state:
s = −(dE_q − dE_0)/q − E_VBM must not sit below −0.7 eV (acceptors) / −1.5 eV (donors; shallow
levels legitimately dip below VBM). Library-wide, s over 12,342 charged states flagged 14 entries
(the rest of the 213 raw hits were already withheld by earlier gates); the two Ef@VBM < −0.5
survivors are q=+2 donors negative only near VBM — genuine Fermi-level pinning. Vac_Ba now shows
q=−2 withheld with the reason, −1/0/+1/+2 intact (1.08/1.09/1.23/1.41 at S-rich).

**"In_Ag shows 2 defect sites in the main window":** for an antisite, `cellPartCounts` counts the
vacated host site as a vacancy ({atoms:1, vac:1}), disagrees with the label ({1,0}), wins, and
`nparts = atoms+vac = 2` went to the viewer, which highlights that many sites. The main window now
derives nparts from the cell-truth `dn` (sites = atoms added + rings for NET-missing only):
In_Ag → 1, vacancies → 1, the S_Ge mislabeled-cell case → 1 ring, unchanged.

Live build 366cbc3c40e0, 10/10 browser-verified (Vac_Ba withheld+reason, In_Ag nparts 1 with
"defect site in black" singular, Vac_In control 1); commits 824551510 + 53e2dc14f (a stray probe
script briefly entered the repo in 824551510 and was removed in the next commit — guard: never
create scratch files inside the repo checkout; scratch lives in the session scratchpad).

## 2026-08-18 — "Cd-Se-Te has no data": the search was substring-only

The data was always there (45 bulk ordering-rows across PBE/PBEsol/HSE06/HSE+SOC and 1,235 defect
rows for the Cd-Se-Te system), but the alloys are named `CdSe0.25Te0.75` / `Cd108Se27Te81`, so the
substring search could never match "CdSeTe" or "Cd-Se-Te" and both explorers looked empty. Fix
(build dd10e7499915, commit fc80b306d): a query that parses entirely as element symbols (capital
split first, greedy two-letter fallback for lowercase) also matches rows whose ELEMENT SET equals
the queried set — "CdSeTe", "Cd-Se-Te", "cd se te", "cdsete" all return the full system in the
Compounds and Defect Explorers, while "CdTe" stays at its 22 substring rows (exact-set rule, no
alloy flooding). Live 10/10: compounds 45/45, defects 1,136/1,136 (pbesol+hse_soc default
checkboxes; 1,235 with all theories).

### DFT status 2026-08-18 03:00
- Defect statics 12/4,995 done (Vac_Ag full ladder + Vac_Ga +2/Neutral + Vac_Al ladder in flight), bulk HSE06 PDOS 5/1,897; 4 highmem jobs running, feeder loop alive on login02.
- pdos_b slice 4 (Ag2Ba0.5Zn0.5Ge1Te4_stannite) hit the 4 h TIMEOUT → resubmitted with -t 12:00:00 (job 15335804); feeder now submits all pdos jobs with 12 h (ddos keeps 4 h — they finish in 15–45 min).
- Website today: footing-aware bulk energetics (e13c38ab1a17), defect ladder gates + twin dedup (366cbc3c40e0 side), transition-level gate + antisite nparts, chemical-system search (dd10e7499915) — all live, each 10/10 browser-verified.
