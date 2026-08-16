"""Site payload, built from the derived products only -- no CSV, no hand-patching.

Reads   log/derived_bulk.json, log/derived_defect.json, log/chempot.json,
        log/dos_*.jsonl, log/steps_*.jsonl
Writes  log/payload/data.json         compounds + defects + refs + key lists
        log/payload/dos/<key>.json.gz element-projected DOS
        log/payload/runs/<key>.json.gz INCAR + POTCAR + KPOINTS + per-ionic-step E and Fmax
        log/payload/optics.json.gz     eps tensor + alpha(E) per key
        log/payload/chempot.json.gz    the polytope vertices, per theory and host

Conventions kept from the shipped site so the existing structures/ and trajs/ payloads keep
resolving: theory labels are PBE / PBEsol / HSE06 / HSE+SOC, and the structure key is built by
the same branch table the template uses.

The -N suffix on a compound (kesterite-3, stannite-12) is a separate relaxation stage or SQS
ordering of the SAME material. One row is published per (theory, compound, polymorph) using the
lowest F/atom -- the ground state -- with the configuration count and the spread carried as
provenance, never averaged.
"""
import os, re, json, glob, gzip, math, collections

B    = "/eagle/wbg_defects/chalcogenide_defects"
LOG  = f"{B}/log"
OUT  = f"{LOG}/payload"
os.makedirs(f"{OUT}/dos", exist_ok=True)
os.makedirs(f"{OUT}/runs", exist_ok=True)

THEORY = {"PBE": "PBE", "PBEsol": "PBEsol", "HSE": "HSE06", "HSE+SOC": "HSE+SOC"}
FK     = {"PBE": "pbe", "PBEsol": "pbesol", "HSE06": "hse", "HSE+SOC": "hse_soc"}
POLY   = re.compile(r"^(?P<base>.+?)_(?P<poly>kesterite|stannite|zincblende|zinc blende|wurtzite|"
                    r"rocksalt|chalcopyrite|reference)(?:-(?P<cfg>\d+))?$")


def split_name(compound):
    """'Ag1In1Se2_kesterite-3' -> ('Ag1In1Se2', 'kesterite', '3').  A name with no recognised
    polymorph suffix is left whole; inventing a split here is how directory names got mangled
    earlier in this project."""
    m = POLY.match(compound)
    if not m:
        m2 = re.match(r"^(?P<base>.+?)-(?P<cfg>\d+)$", compound)
        if m2:
            return m2.group("base"), "reference", m2.group("cfg")
        return compound, "reference", None
    p = m.group("poly")
    return m.group("base"), ("zinc blende" if p == "zincblende" else p), m.group("cfg")


def struct_key(name, theory, ord_):
    """The template's own branch table, reproduced exactly -- see FK/RK in template.html."""
    RK = {"PBEsol": "PBEsol", "HSE06": "HSE", "HSE+SOC": "HSE+SOC"}.get(theory)
    if ord_ == "zinc blende":
        return f"{FK[theory]}__{name}"
    if theory == "HSE+SOC":
        return f"{name}_{ord_}"
    if theory == "PBEsol":
        return f"PBEsol__{name}_{ord_}"
    if theory == "HSE06":
        return f"HSE06__{name}_{ord_}"
    return f"pbe__{name}_{ord_}"          # new branch; the template gets the matching case


def n_formula_units(comp):
    """gcd over the integer stoichiometry; fractional alloy sites make it 1."""
    vals = list(comp.values())
    if not vals or any(abs(v - round(v)) > 1e-6 for v in vals):
        return 1
    g = 0
    for v in vals:
        g = math.gcd(g, int(round(v)))
    return max(g, 1)


# --------------------------------------------- steps and dos, indexed by (theory, compound)
# derived_bulk carries no path, so the run is matched on (theory, compound) and, where a compound
# has several variant directories, on the one whose total energy matches the published ground
# state. Picking the first would silently pair a compound's numbers with a different run's inputs.
def index_jsonl(pattern):
    idx = collections.defaultdict(list)
    n = 0
    for f in sorted(glob.glob(f"{LOG}/{pattern}")):
        for line in open(f):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("compound") and r.get("theory"):
                idx[(r["theory"], r["compound"])].append(r)
                n += 1
    return idx, n


steps, n_steps_rec = index_jsonl("steps_*.jsonl")
dos, n_dos_rec = index_jsonl("dos_*.jsonl")
print(f"steps records {n_steps_rec}  dos records {n_dos_rec}")


def pick(idx, theory, compound, F):
    """the variant whose energy matches the ground state we are publishing"""
    cands = idx.get((theory, compound))
    if not cands:
        return None
    if len(cands) == 1 or F is None:
        return cands[0]
    with_F = [c for c in cands if c.get("F") is not None]
    if not with_F:
        return cands[0]
    return min(with_F, key=lambda c: abs(c["F"] - F))

# ---------------------------------------------------------------- bulk -> compounds
bulk = json.load(open(f"{LOG}/derived_bulk.json"))
print(f"derived bulk rows {len(bulk)}")

groups = collections.defaultdict(list)
for key, r in bulk.items():
    base, poly, cfg = split_name(r["compound"])
    groups[(THEORY[r["theory"]], base, poly)].append((key, r, cfg))

compounds, optics = [], {}
byname = collections.defaultdict(dict)         # (theory, name) -> {ord: row}
n_dos = n_runs = 0

for (theory, name, poly), members in sorted(groups.items()):
    members.sort(key=lambda t: (t[1]["F_per_atom"], t[0]))
    key, r, _ = members[0]                     # ground state
    fpa = [m[1]["F_per_atom"] for m in members]
    spread = round((max(fpa) - min(fpa)) * 1000, 3) if len(fpa) > 1 else 0.0

    comp = r.get("composition") or {}
    nfu = n_formula_units(comp)
    edec = r.get("E_decomp_per_atom")
    edec_fu = round(edec * r["natoms"] / nfu, 4) if edec is not None else None

    st = pick(steps, r["theory"], r["compound"], r.get("F"))
    dr = pick(dos, r["theory"], r["compound"], r.get("F"))
    fmax = None
    if st and st.get("steps"):
        fmax = st["steps"][-1].get("fmax")

    eps3 = None
    if r.get("eps_xx") is not None:
        eps3 = [round(r["eps_xx"], 4), round(r["eps_yy"], 4), round(r["eps_zz"], 4)]

    row = [
        r.get("Ef_per_atom"),                                   # 0 formation energy, eV/atom
        edec_fu,                                                # 1 decomposition energy, eV/f.u.
        r.get("gap"),                                           # 2 band gap
        r.get("eps_avg"),                                       # 3 dielectric constant
        None,                                                   # 4 SLME -- see note below
        r.get("F"),                                             # 5 total energy
        r.get("natoms"),                                        # 6 atoms in the cell
        "",                                                     # 7 (reserved, shipped empty)
        [round(r[k], 4) for k in ("a", "b", "c")] if r.get("a") else None,   # 8 lattice
        None,                                                   # 9 entropy term
        fmax,                                                   # 10 final max force
        r.get("vbm"),                                           # 11
        r.get("cbm"),                                           # 12
        eps3,                                                   # 13 dielectric tensor
        None,                                                   # 14 SLME(thickness)
        r.get("direct"),                                        # 15 direct gap?
        r.get("eps_source"),                                    # 16 where eps came from
        r.get("kmesh"),                                         # 17
        [round(r[k], 2) for k in ("alpha", "beta", "gamma")] if r.get("alpha") else None,  # 18
        r.get("decomposes_to"),                                 # 19 the phases it decomposes to
        len(members),                                           # 20 configurations merged
        spread,                                                 # 21 spread across them, meV/atom
        r.get("paw"),                                           # 22 PAW potentials
    ]
    byname[(theory, name)][poly] = row

    sk = struct_key(name, theory, poly)
    if dr:
        blob = {"ef": dr.get("ef"), "e": dr.get("e"), "total": dr.get("total"),
                "el": dr.get("el") or {}, "projected": bool(dr.get("projected"))}
        with gzip.open(f"{OUT}/dos/{sk}.json.gz", "wt") as fh:
            json.dump(blob, fh, separators=(",", ":"))
        n_dos += 1
    if st:
        blob = {"F": st.get("F"), "kmesh": st.get("kmesh"), "potcar": st.get("potcar"),
                "incar": st.get("incar"), "ediffg": st.get("ediffg"),
                "n_steps": st.get("n_steps"), "steps": st.get("steps"),
                "force_converged": st.get("force_converged"),
                "reached_required_accuracy": st.get("reached_required_accuracy")}
        with gzip.open(f"{OUT}/runs/{sk}.json.gz", "wt") as fh:
            json.dump(blob, fh, separators=(",", ":"))
        n_runs += 1
    if r.get("abs_E") and r.get("abs_alpha"):
        # alpha(E) as [E, alpha] pairs, which is the shape the detail panel already reads
        optics[sk] = {"abs": [[e, a] for e, a in zip(r["abs_E"], r["abs_alpha"])],
                      "slme": None, "eps": eps3, "source": r.get("alpha_source")}

for (theory, name), ords in sorted(byname.items()):
    # the published polymorph is the most stable one that HAS a formation energy
    scored = [(o, v) for o, v in ords.items() if v[0] is not None]
    best = min(scored, key=lambda t: t[1][0])[0] if scored else sorted(ords)[0]
    rec = {"n": name, "f": theory, "o": ords, "b": best}
    if theory == "HSE06":
        rec["rk"] = "HSE06 (A2BCX4)"
    compounds.append(rec)

print(f"compounds {len(compounds)}  dos files {n_dos}  run files {n_runs}  optics {len(optics)}")

# ---------------------------------------------------------------- defects
#
# dE (E_defect,q - E_pristine) is the SAME across every vertex of a given defect+charge -- it
# excludes the chemical-potential term entirely. Ef_VBM/Ef_CBM DO vary by vertex, since they add
# that vertex's own mu solve: Ef_VBM = dE + sum(n_i*mu_i) + q*E_VBM, Ef_CBM = Ef_VBM + q*gap. Using
# a single arbitrary "first vertex" to define which charge states exist (the previous r["e"]) meant
# a defect with a real archived trajectory but an unresolved chem-pot vertex silently lost its
# charge ladder, its movie button, and its transition levels -- three unrelated features died from
# one field. r["e"] is now keyed from dE (vertex-independent), so archived-but-unsolved defects
# still show their raw physics; only the chemical-potential-dependent Ef(E_F) plot needs a vertex.
dd = json.load(open(f"{LOG}/derived_defect.json"))
dd = list(dd.values()) if isinstance(dd, dict) else dd
defects = []
for r in dd:
    theory = THEORY.get(r["theory"], r["theory"])
    vx = {}
    e = {}
    corr = {}
    for vname, v in (r.get("vertices") or {}).items():
        ch = {}
        for cname, c in (v.get("charges") or {}).items():
            q = str(c["q"])
            ch[q] = {"dE": c.get("dE"), "vbm": c.get("Ef_VBM"), "cbm": c.get("Ef_CBM"),
                     "note": c.get("note")}
            if c.get("dE") is not None and q not in e:
                e[q] = c["dE"]
            if q not in corr:
                corr[q] = bool(c.get("corrected"))
        vx[vname] = {"facet": v.get("facet") or [], "q": ch}
    # a vertex is USABLE for the Ef(E_F) plot only if it actually solved (has vbm/cbm, not just
    # the elemental-rich fallback that ships dE with vbm/cbm left null)
    usable = [vn for vn, v in vx.items()
              if any(c.get("vbm") is not None for c in v["q"].values())]
    defects.append({
        "f": FK.get(theory, theory), "h": r["host"], "d": r["defect"],
        "t": r.get("host_bulk_match", "raw"),
        "g": r.get("host_gap"), "v": r.get("host_vbm"),
        "e": e, "corr": corr,
        "src": f"raw ({r.get('host_bulk_match')})",
        "u": None, "rq": None,
        "dn": r.get("dn"), "nat": r.get("natoms"),
        "nc": r.get("n_configs"), "sp": r.get("config_spread_meV"),
        "vx": vx, "vxu": usable, "tl": r.get("transition_levels") or [],
        "gs": r.get("ground_state"),
    })
print(f"defects {len(defects)}  ({sum(1 for d in defects if d['vxu'])} with a resolved chem-pot vertex)")

# ---------------------------------------------------------------- refs from the chem-pot build
cp = json.load(open(f"{LOG}/chempot.json"))
refs = {}
for th, o in cp.items():
    refs[THEORY.get(th, th)] = {"el": o.get("mu0", {}), "bin": {}}

data = {
    "defects": defects,
    "compounds": compounds,
    "refs": refs,
    "structKeys": sorted(struct_key(n, t, o) for (t, n), ords in byname.items() for o in ords),
    "trajKeys": [],
    "dosKeys": sorted(os.path.splitext(os.path.splitext(f)[0])[0]
                      for f in os.listdir(f"{OUT}/dos")),
    "runKeys": sorted(os.path.splitext(os.path.splitext(f)[0])[0]
                      for f in os.listdir(f"{OUT}/runs")),
}
with open(f"{OUT}/data.json", "w") as fh:
    json.dump(data, fh, separators=(",", ":"))
with gzip.open(f"{OUT}/optics.json.gz", "wt") as fh:
    json.dump(optics, fh, separators=(",", ":"))
with gzip.open(f"{OUT}/chempot.json.gz", "wt") as fh:
    json.dump(cp, fh, separators=(",", ":"))

print("wrote", OUT)
for f in ("data.json", "optics.json.gz", "chempot.json.gz"):
    print(f"  {f} {os.path.getsize(f'{OUT}/{f}'):,} bytes")
print(f"  dos/ {len(data['dosKeys'])} files   runs/ {len(data['runKeys'])} files")
