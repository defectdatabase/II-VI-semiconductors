# Telluride website audit — 2026-08-16

Target: **<https://material-hub.github.io/telluride/>** (live deployment) and its source in this repo.

Scope: `site_src/template.html` (= `docs/index.html`), `site_src/build_site.py`,
`docs/pages/structgrid/index.html`, `docs/pages/traj/index.html`, `viewer_src/`,
`middleware/invoke`, cross-checked against `docs/data.json` (4,371 defect rows, 13,959 compound
rows, 20,219 structure keys, 8,941 trajectory keys, 26,614 DOS keys).

## Live-site verification (2026-08-16)

- The served `index.html` is **byte-identical** to `docs/index.html` in this repo
  (build `ec9086a5bf09`, matching `version.json`). Every code finding below is live.
- All asset classes return 200: `data.json` (17.0 MB, but **2.06 MB on the wire** — GitHub Pages
  gzips it), `chempot.json.gz`, `optics.json.gz` (20.4 MB), `structures/`, `trajs/`, `dos/`,
  `figures/`, both vendored viewer pages and their hashed JS/CSS bundles.
- `.json.gz` payloads are served as `application/gzip` *without* `Content-Encoding`, so the
  browser receives raw gzip bytes and the `DecompressionStream("gzip")` path is correct.
- External links all resolve: `github.com/material-hub/telluride` (+`/issues`), the nanoHUB tool
  page, and the Plotly CDN all return 200. The ten DOI reference links resolve (several publishers
  answer curl with 403 — bot protection, not broken links).
- Concrete live examples of the severe bugs below:
  - vacancy row with an archived trajectory, unreachable from the vacancy pill:
    `trajs/pbesol__Ag1Al0.5Ga0.5Se2_kesterite__Vac_Al.json.gz` returns 200 (#2);
  - `Vac_In in Ag1Ga0.5In0.5S2` (PBEsol) hits the fake-`Vac`-element path (#7);
  - `Bi_Se+O_i in CdSe0.06Te0.94` is one of the 320 hidden HSE+SOC defect rows (#1).

Data reference — defect rows per theory: pbesol 2,732 · hse 491 · pbe 762 · pbe_u 66 · hse_soc 320.
Compounds per theory: PBEsol 5,018 · HSE+SOC 4,869 · HSE06 3,874 · PBE 194 · PBE+U 4.

---

## Severe — user-facing, live now

### 1. HSE+SOC defect checkbox is a no-op; all 320 HSE+SOC defect rows are hidden

The payload spells the theory `hse_soc` (with underscore); the filter and the coverage
counter spell it `hsesoc`. `fs.has("hse_soc")` is never true.

- `site_src/template.html:776` — `if(document.getElementById("ck-hsesoc").checked)fs.add("hsesoc");`
- `site_src/template.html:834` — `nH=DEFECTS.filter(r=>r.f==="hsesoc").length` (always 0, so the
  coverage strip literally prints "HSE+SOC 0")
- Everywhere else is correct: `THEORY` (line 690), `hostStructKeys` (1731–1745), `structKeyOf` (1644).

Consequence: the Defect Explorer can only ever show the 2,732 PBEsol rows; the HSE+SOC checkbox
toggles nothing, and defect-level HSE+SOC formation energies are unreachable.

Fix: `"hsesoc"` → `"hse_soc"` in both places (the checkbox `id` can stay).

### 2. "vacancy" filter pill shows ZERO rows; 591 vacancy defects are filed under "substitution"

Same `Vac_` rename bug the comments describe for `classify()` (fixed at line 731) and
`defectPartCounts()` (fixed at line 1841) — but `structClasses()` was never updated:

- `site_src/template.html:737` — `if(p.startsWith("V_")) set.add("vacancy");`

`"Vac_Cd".startsWith("V_")` is false, so execution falls to `p.includes("_")` → tagged
"substitution". Measured against `data.json`:

- 683 of 691 vacancy-containing defects use `Vac_`; the 8 legacy `V_` rows are all hse/pbe
  (hidden by the theory gate, see #1/#8) → the vacancy pill renders an **empty table**.
- 591 visible (PBEsol) vacancy rows wrongly appear under the "substitution" pill.

Fix: `if(p.startsWith("V_")||p.startsWith("Vac_")) set.add("vacancy");`

### 3. Virtualized table rows: JS pitch is 34 px, CSS height is 26 px

- `site_src/template.html:802` — `const ROWH=34,VIEWH=560;`
- `site_src/template.html:91` — `.trow{...height:34px;...}`
- `site_src/template.html:327` — `.trow{height:26px}` (later rule, same specificity → wins)

Every row is positioned at `top: i*34px` but renders 26 px tall: an 8 px dead (non-clickable)
gap under every row, and the spacer/scrollbar is ~30% taller than the content. Affects both the
defect and compound tables. Fix one side: `ROWH=26` (presumably the intent of the density pass)
or drop the 26 px override.

### 4. Toggle-closing a row leaves the dark backdrop up

- `site_src/template.html:841` — `dOpenDetail` toggle path removes `on` from `#detail` only.
- `site_src/template.html:1440` — `cOpenDetail` toggle path removes `on` from `#cdetail` only.

Neither removes `on` from `#modalback`, so the page stays dimmed and click-blocked until the
user happens to click the backdrop (which calls `closeModals`). Add
`document.getElementById("modalback").classList.remove("on");` to both paths.

### 5. A malformed `?tab=` URL kills the whole page

- `site_src/template.html:751-753`

```js
const urltab=new URLSearchParams(location.search).get("tab");
if(urltab&&document.querySelector(`#tabbar .tab[data-v="${urltab}"]`))
  document.querySelector(`#tabbar .tab[data-v="${urltab}"]`).click();
```

`urltab` is interpolated into a selector unescaped. A value containing `"` or `]` (e.g. a shared
link with `?tab=x%22`) makes `querySelector` throw a `SyntaxError` at top level, aborting the
entire script — `boot()` never runs, leaving blank tables and dead tabs. Wrap in try/catch or
validate against the known set `{rankings,explorer,tool,methods}` first.

---

## Moderate

### 6. PBE+U compounds can never show their relaxation movie

- `site_src/template.html:1267-1270` — `cMovieKey`'s `FKEY` map omits `"PBE+U"`, so the key
  becomes `host__undefined__In2S4Zn`. (The sibling map in `structKeyOf`, line 1644, has it.)

Verified: all 4 PBE+U compounds (`In2S4Zn`, `In37S72Zn17`, `ZnIn2S4`, `ZnIn2S4_H`) have archived
`host__pbe_u__*` trajectories, but the "▶ Relaxation movie" button never renders; they fall back
to "View static calculation". The "Relaxation movie" availability filter undercounts by the same 4.
Fix: add `"PBE+U":"pbe_u"` to `FKEY`.

### 7. `unrelaxedDefectModel` creates a fake element "Vac"

- `site_src/template.html:1148-1156` — vacancy removal tests `atom==="V"` only; for `Vac_Cd` the
  code takes the substitution branch and writes `species=[{element:"Vac",occu:1}]`, emitting a CIF
  with a non-existent element to the viewer instead of a missing atom.

Affects the 53 visible (PBEsol) `Vac_*` rows that have no archived trajectory (100 across all
theories). Fix: `if(atom==="V"||atom==="Vac") st.sites.splice(idx,1);`

### 8. 1,319 defect rows (30% of the payload) are unreachable in the UI

The filter row only has PBEsol and HSE+SOC checkboxes (`site_src/template.html:775-776`), so the
491 `hse`, 762 `pbe`, and 66 `pbe_u` defect rows can never be displayed — yet `topstats`
(line 2860) advertises all 4,371 entries, and the rows are shipped in the 17 MB `data.json`.
Either add the missing theory checkboxes (`THEORY` already has the labels) or stop shipping the
rows.

### 9. Structure-viewer races on fast clicks / slow networks

- `mountStructure` (`site_src/template.html:1656-1678`): no `cSel!==r` staleness check after the
  `fetch` at line 1671 — a slow structure fetch clobbers a newer selection.
- `mountDefectStructure` (`site_src/template.html:1160-1229`): checks `dSel!==r` at lines 1167 and
  1195, but not after the multi-fetch `pickHostForDefect` await at line 1203 — a late resolve
  overwrites the newer defect's structure *and* the shared `DSTRUCT_MARKS`/`DSTRUCT_VAC` the movie
  button reads (the race the lines 1002–1006 comment fixed for the button, but not for the mount).

Fix: re-check selection identity after every await; a monotonically increasing ticket like
`INCAR_TICKET` (line 1545) is the existing pattern.

### 10. Version-stamp reload drops the current tab

- `site_src/template.html:390` — `location.replace(location.pathname+"?v="+v.id+location.hash)`
  discards the existing query string, so a reader on `?tab=methods` or `?tab=rankings` is bounced
  back to the Defect Explorer after the auto-reload. Preserve `location.search` (minus any stale
  `v`) when rebuilding the URL.

---

## Minor / cleanup

- **Dead code shipped in the page** (all in `site_src/template.html`): the old trajbox cluster
  (`mountTraj` line 2010 plus `showFrame`/`playTraj`/`frameDisp`/`dispNote`/`trajStructure`/
  `ampFrame`/`TAMP` — no callers; only `stopTraj` is still invoked from `closeModals`);
  `drawStabilityMap` (2547); `INCAR_TXT` (1679 — still contains the "LORBIT was unset, total DOS
  only" claim that line 1596's comment says was wrong); `MV_VIEWS` (1715); `typeAim` (1035);
  `parkStructure` (2179); `defectSiteMark` (1902); `CURKEY` (set at 1659, never read); the `ref__`
  and `"zinc blende"` branches of `structKeyOf` (1646–1647 — no `ref` rows or `zinc blende`
  orderings exist in the payload).
- **Transition-levels panel is computed but never displayed**: `#detail .dgrid>.dcol:nth-child(3)`
  is `display:none!important` (251) and `#dtranswrap` is hidden again in JS (970–972), yet every
  defect open still computes levels, builds the table, and draws the ladder (952–993). Either
  un-hide the column or skip the work.
- **Latent movie-modal issues**: `#mvm-slider`'s `max` is never set in `mvmLoad` (stays at the
  HTML default of 1), and `openStaticMovie` disables the play/prev/next/speed buttons with no
  corresponding re-enable (2144–2145). Currently masked because continuous mode hides `#mvm-body`
  entirely — will bite if the internal controls are ever shown again.
- `cRenderMeta`'s coverage `order` list (1430) omits PBE+U, so the 4 PBE+U compounds are not
  counted in the strip.
- Compound "No. of atoms" and "Lattice parameter" sorts treat missing values as `0`
  (1242–1243), so "—" rows sort first when ascending, unlike the nulls-last convention used by
  every other column (and by the defect table).
- `boot()` (2841) has no error handling around the `data.json` fetch — a failed fetch leaves a
  silently empty page. (The payload is 17 MB but 2.06 MB on the wire thanks to GitHub Pages gzip;
  still ~17 MB of JSON to parse. Consider a visible error note, and possibly splitting the payload
  — the PBE/hse/pbe_u defect rows are never read, see #8.)
- `VIEWH=560` (802) vs `.tview{height:min(66vh,760px)}` (329): on viewports taller than ~1130 px
  the rendered window can leave a small uncovered sliver at the bottom until the next scroll event.
- `drawDOSUnavailable`'s `"total-only"` branch (2467) is unreachable — `drawDOS` never returns
  that status (it draws the total curve itself and returns `"projected"`).

---

## Verified OK

- `docs/index.html` vs `site_src/template.html`: identical except `__BUILD_ID__` stamp.
- `build_site.py` dangling-key trim logic, build stamping, version.json write.
- Key-resolution hit rates (via `structKeyOf` replica against `data.json`): structures
  20,212/20,225, DOS 20,364/22,509 (misses are genuinely un-archived and handled gracefully),
  runs 20,230/20,232. Compound movie keys hit wherever a `host__*` trajectory exists
  (except PBE+U, see #6).
- `docs/pages/structgrid` and `docs/pages/traj` shells, their postMessage contracts, the
  tooltip `pointer-events` flicker fix, and the standalone-traj close button.
- Null-gap defect rows (54) — all have empty `vxu`, so `dRedrawPlot` exits before the
  `r.g.toFixed` that would otherwise throw.
- `middleware/invoke` and `config.yml` are consistent (`Cd_Zn_X_v3.ipynb`, tool `defectdatabase`).
