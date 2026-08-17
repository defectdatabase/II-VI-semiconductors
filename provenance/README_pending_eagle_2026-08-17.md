
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
