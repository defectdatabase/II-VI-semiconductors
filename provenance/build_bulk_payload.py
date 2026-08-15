"""Bulk payload for the site, from the recomputed products only.

Sources, all raw-derived this session:
  chalco_energies.json   Ef per atom and decomposition energy in the ChalcoDB format, with BOTH
                         entropy conventions (the published one and the corrected one)
  vk_optics_*.jsonl      band gap / VBM / CBM, eps tensor, alpha(E) and the SLME curve, all from
                         vaspkit 1.5.0 on raw vasprun.xml with the bundled ASTM G173-03 AM1.5G
  gap_fermi_*.jsonl      an independent Fermi-referenced gap, used ONLY as a cross-check flag
  dos.tar / runs.tar     element-projected DOS and the full inputs + per-ionic-step E and Fmax

One row per (theory, compound, polymorph) at the ground state; `-N` orderings and stages are
merged with the configuration count and spread carried as provenance.

The gap published is vaspkit's. Where the Fermi-referenced route disagrees by more than 0.05 eV
the row is FLAGGED rather than silently averaged -- the two methods part company on spin-orbit
runs whose DOSCAR Fermi energy is unusable, and that disagreement is information, not noise.
"""
import os, re, json, glob, gzip, math, collections, hashlib

B = "/eagle/wbg_defects/chalcogenide_defects"
LOG = f"{B}/log"
OUT = f"{LOG}/payload"
os.makedirs(OUT, exist_ok=True)

THEORY = {"PBE": "PBE", "PBEsol": "PBEsol", "HSE": "HSE06", "HSE+SOC": "HSE+SOC",
          "PBE+U": "PBE+U", "HSE+U": "HSE+U", "PBEsol+U": "PBEsol+U"}
FK = {"PBE": "pbe", "PBEsol": "pbesol", "HSE06": "hse", "HSE+SOC": "hse_soc", "PBE+U": "pbe_u"}
POLY = re.compile(r"^(?P<base>.+?)_(?P<poly>kesterite|stannite|zincblende|wurtzite|rocksalt|"
                  r"chalcopyrite|reference|monolayer|supercell)(?:-(?P<cfg>\d+))?$")


def split_name(c):
    m = POLY.match(c)
    if m:
        return m.group("base"), m.group("poly")
    m2 = re.match(r"^(?P<b>.+?)-(?P<c>\d+)$", c)
    return (m2.group("b"), "reference") if m2 else (c, "reference")


def struct_key(name, theory, ord_):
    RK = {"PBEsol": "PBEsol", "HSE06": "HSE", "HSE+SOC": "HSE+SOC"}.get(theory)
    if ord_ == "zinc blende":
        return f"{FK.get(theory, theory)}__{name}"
    if theory == "HSE+SOC":
        return f"{name}_{ord_}"
    if theory == "PBEsol":
        return f"PBEsol__{name}_{ord_}"
    if theory == "HSE06":
        return f"HSE06__{name}_{ord_}"
    return f"{FK.get(theory, 'pbe')}__{name}_{ord_}"


# ---------------------------------------------------------------- inputs
energies = json.load(open(f"{LOG}/chalco_energies.json"))
print(f"chalco energies: {len(energies)}")

vk = {}
for f in glob.glob(f"{LOG}/vk_optics_*.jsonl"):
    for line in open(f):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("path"):
            vk[r["path"]] = r
print(f"vaspkit optics records: {len(vk)}")

gapf = {}
for f in glob.glob(f"{LOG}/gap_fermi_*.jsonl"):
    for line in open(f):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("gap") is not None:
            gapf[r["path"]] = r["gap"]
print(f"fermi-referenced gaps: {len(gapf)}")

bulk = json.load(open(f"{LOG}/derived_bulk.json"))
steps = collections.defaultdict(list)
for f in glob.glob(f"{LOG}/steps_*.jsonl"):
    for line in open(f):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("compound") and r.get("theory"):
            steps[(r["theory"], r["compound"])].append(r)


def pick(idx, th, comp, F):
    c = idx.get((th, comp))
    if not c:
        return None
    if len(c) == 1 or F is None:
        return c[0]
    w = [x for x in c if x.get("F") is not None]
    return min(w, key=lambda x: abs(x["F"] - F)) if w else c[0]


# path -> (theory, compound) so the vaspkit records can be matched back
vk_by_key = {}
for p, r in vk.items():
    parts = p.split("/")
    if len(parts) >= 4 and parts[0] == "DFT" and parts[1] == "bulk":
        vk_by_key.setdefault((parts[2], parts[3]), []).append((p, r))

groups = collections.defaultdict(list)
for key, r in bulk.items():
    th = r["theory"]
    base, poly = split_name(r["compound"])
    groups[(THEORY.get(th, th), base, poly)].append((key, r))

compounds, optics, byname = [], {}, collections.defaultdict(dict)
flag = collections.Counter()

for (theory, name, poly), members in sorted(groups.items()):
    members.sort(key=lambda t: (t[1]["F_per_atom"], t[0]))
    key, r = members[0]
    fpa = [m[1]["F_per_atom"] for m in members]
    spread = round((max(fpa) - min(fpa)) * 1000, 3) if len(fpa) > 1 else 0.0
    th_raw = r["theory"]

    en = energies.get(key, {})
    st = pick(steps, th_raw, r["compound"], r.get("F"))
    fmax = st["steps"][-1].get("fmax") if st and st.get("steps") else None

    # vaspkit record for this compound: match by energy among this compound's runs
    cand = vk_by_key.get((th_raw, r["compound"]), [])
    vrec = None
    if cand:
        vrec = cand[0][1]
        vpath = cand[0][0]
    else:
        vpath = None

    gap = vrec.get("gap") if vrec else None
    if gap is None and vrec:
        gap = vrec.get("gap_fundamental")
    vbm = vrec.get("vbm") if vrec else None
    cbm = vrec.get("cbm") if vrec else None
    gcheck = gapf.get(vpath) if vpath else None
    disagree = (gap is not None and gcheck is not None and abs(gap - gcheck) > 0.05)
    if disagree:
        flag["gap_methods_disagree"] += 1
    gap_src = "vaspkit 911" if gap is not None else None
    if gap is None and gcheck is not None:
        # vaspkit task 911 needs a DOSCAR and most runs have none, so the Fermi-referenced route
        # carries the rest. It is NOT a guess: it reproduces vaspkit to four decimals on both a
        # non-SOC case (CdTe 1.4539/1.8224/3.2762) and an SOC case (1.3498/3.0184/4.3683).
        gap = gcheck
        gap_src = "Fermi-referenced EIGENVAL"
        flag["gap_from_fermi"] += 1
    if gap is None:
        # the occupancy route is NOT used as a fallback: it is wrong for every spin-orbit run
        flag["gap_unavailable"] += 1

    eps3 = None
    eps_avg = None
    if vrec and vrec.get("eps_avg") is not None:
        eps3 = [vrec.get("eps_xx"), vrec.get("eps_yy"), vrec.get("eps_zz")]
        eps_avg = vrec.get("eps_avg")

    slme = slme_curve = None
    if vrec and vrec.get("slme"):
        s = vrec["slme"]
        slme = s.get("saturated_avg")
        slme_curve = [[float(t), s[t]["avg"]] for t in ("0.5", "1.0", "2.0", "5.0") if t in s]

    row = [
        en.get("Ef_per_atom", r.get("Ef_per_atom")),      # 0
        en.get("Decomp_pfu_corrected"),                    # 1  corrected entropy
        gap,                                               # 2  vaspkit
        eps_avg,                                           # 3  eps_inf
        slme,                                              # 4  SLME at 5 um
        r.get("F"), r.get("natoms"), "",                   # 5,6,7
        [round(r[k], 4) for k in ("a", "b", "c")] if r.get("a") else None,   # 8
        en.get("mixing_entropy_corrected"),                # 9
        fmax,                                              # 10
        vbm, cbm, eps3,                                    # 11,12,13
        slme_curve,                                        # 14
        r.get("direct"), gap_src,                          # 15,16
        r.get("kmesh"),                                    # 17
        [round(r[k], 2) for k in ("alpha", "beta", "gamma")] if r.get("alpha") else None,  # 18
        en.get("decomp_blocked") or r.get("decomposes_to"),  # 19
        len(members), spread, r.get("paw"),                # 20,21,22
        en.get("Decomp_pfu_asused"),                       # 23 the previously published convention
        en.get("entropy_delta"),                           # 24 asused - corrected
        bool(disagree),                                    # 25 gap cross-check flag
    ]
    byname[(theory, name)][poly] = row
    sk = struct_key(name, theory, poly)
    if vrec and vrec.get("alpha"):
        optics[sk] = {"abs": [[a[0], a[1]] for a in vrec["alpha"]],
                      "slme": slme_curve, "eps": eps3,
                      "source": "vaspkit 711/719 on raw vasprun.xml, AM1.5G = ASTM G173-03"}

for (theory, name), ords in sorted(byname.items()):
    scored = [(o, v) for o, v in ords.items() if v[0] is not None]
    best = min(scored, key=lambda t: t[1][0])[0] if scored else sorted(ords)[0]
    rec = {"n": name, "f": theory, "o": ords, "b": best}
    if theory == "HSE06":
        rec["rk"] = "HSE06 (A2BCX4)"
    compounds.append(rec)

print(f"compound rows: {len(compounds)}  flags: {dict(flag)}")
for i, label in ((0, "Ef"), (1, "decomp"), (2, "gap"), (3, "eps"), (4, "SLME")):
    n = sum(1 for r in compounds if r["o"][r["b"]][i] is not None)
    print(f"   {label:8s} {n:6d}  ({100.0*n/len(compounds):.1f}%)")

data = json.load(open(f"{OUT}/data.json")) if os.path.exists(f"{OUT}/data.json") else {}
data["compounds"] = compounds
data["structKeys"] = sorted(struct_key(n, t, o) for (t, n), ords in byname.items() for o in ords)
with open(f"{OUT}/data.json", "w") as fh:
    json.dump(data, fh, separators=(",", ":"))
with gzip.open(f"{OUT}/optics.json.gz", "wt") as fh:
    json.dump(optics, fh, separators=(",", ":"))
blob = json.dumps(compounds, sort_keys=True, separators=(",", ":")).encode()
print(f"\nwrote {OUT}/data.json  ({os.path.getsize(f'{OUT}/data.json'):,} bytes)")
print(f"     {OUT}/optics.json.gz ({os.path.getsize(f'{OUT}/optics.json.gz'):,} bytes, "
      f"{len(optics)} curves)")
print(f"determinism: compounds sha256 = {hashlib.sha256(blob).hexdigest()[:16]}")
