
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
