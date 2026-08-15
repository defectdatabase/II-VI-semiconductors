"""Defect formation energies, assembled exactly as dft-defects.md L1 specifies.

    E_f[X^q](E_F) = E_tot[X^q] - E_tot[pristine]        same cell, same settings
                  + Sum_i n_i mu_i                      n_i = atoms REMOVED (added -> n_i < 0)
                  + q (E_VBM + E_F)
                  + E_corr(q)                           = E_lattice(q) - q dV_align

Every input is measured from the run tree, and the three things that went wrong before are
each closed by a check rather than a convention:

  pristine   matched by LATTICE to the defect cells, not by directory name. For PBEsol CdTe the
             name-matched bulk is 0.84 eV away from the cell-matched one.
  dn         derived from the defect cell's COMPOSITION against that pristine, then cross-checked
             against NELECT through the PAW ZVALs. Directory labels are provenance only -- 15 of
             them were backwards.
  E_corr     alpha_M by Ewald on the ACTUAL supercell (gated: sc 2.837297, fcc 2.888282,
             bcc 2.888462, gamma-independent to 1e-9), L = V^(1/3), eps per host from a table
             that records where each value came from, and dV from the OUTCAR core potentials in
             the far region. A host with no sourced eps gets NO image term and says so; it never
             silently inherits another host's constant.
"""
import os, re, sys, gzip, json, math, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ewald import madelung, gates, HARTREE_ANG

B = "/eagle/wbg_defects/chalcogenide_defects"
LOG = f"{B}/log"
ONLY = sys.argv[1] if len(sys.argv) > 1 else None      # "PBEsol/CdTe" to benchmark one host

# --- static dielectric constants -------------------------------------------------------------
# Each entry records WHAT the number is, because the charge correction is only as good as this.
# "expt"  = measured, with the citation.  "dfpt" = this project's own ph.x eps_inf + Gonze-Lee
# ionic term (kosmos/DFT/_tables/host_eps_static.json).  Alloys are Vegard-interpolated between
# their binary parents and flagged as such -- an interpolated eps is a stated approximation.
EPS = {
    "CdTe": (10.31, "expt", "Strzalkowski, Joshi & Crowell, Appl. Phys. Lett. 28, 350 (1976), "
                            "doi:10.1063/1.88755 -- eps_0 = 10.31 +/- 0.08, extrapolated to 0 K"),
    "ZnSe": (8.80,  "expt", "Strzalkowski, Joshi & Crowell, Appl. Phys. Lett. 28, 350 (1976), "
                            "doi:10.1063/1.88755 -- eps_0 = 8.80 +/- 0.07, extrapolated to 0 K"),
    "ZnS":  (9.48,  "dfpt", "kosmos/DFT/_tables/host_eps_static.json ZnS_mp-10695, "
                            "ph.x eps_inf + Gonze-Lee ionic, isotropic"),
}
EPS_ALLOY_PARENTS = {}   # filled below from the host name


def op(p):
    if os.path.exists(p):
        return open(p, errors="ignore")
    if os.path.exists(p + ".gz"):
        return gzip.open(p + ".gz", "rt", errors="ignore")
    return None


def poscar(d):
    """cell (3x3, Angstrom), species list, counts, fractional coordinates"""
    fh = op(f"{d}/CONTCAR") or op(f"{d}/POSCAR")
    if not fh:
        return None
    try:
        lines = fh.read().splitlines()
    finally:
        fh.close()
    if len(lines) < 8:
        return None
    try:
        s = float(lines[1].split()[0])
        cell = [[float(x) * s for x in lines[i].split()[:3]] for i in (2, 3, 4)]
        els = lines[5].split()
        cnt = [int(x) for x in lines[6].split()]
    except (ValueError, IndexError):
        return None
    if not els or not re.fullmatch(r"[A-Z][a-z]?", els[0]):
        return None
    nat = sum(cnt)
    mode = lines[7].strip().lower()
    start = 8
    if mode.startswith("s"):                      # selective dynamics
        mode = lines[8].strip().lower()
        start = 9
    direct = mode.startswith("d")
    coords = []
    for i in range(start, start + nat):
        try:
            v = [float(x) for x in lines[i].split()[:3]]
        except (ValueError, IndexError):
            return None
        coords.append(v)
    if not direct:                                # cartesian -> fractional
        inv = _inv3(cell)
        coords = [[sum(c[k] * inv[k][j] for k in range(3)) for j in range(3)] for c in coords]
    species = []
    for e, n in zip(els, cnt):
        species += [e] * n
    return {"cell": cell, "species": species, "coords": coords,
            "comp": dict(zip(els, cnt)), "natoms": nat}


def _inv3(m):
    a, b, c = m
    det = (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
           + a[2] * (b[0] * c[1] - b[1] * c[0]))
    return [[(b[1] * c[2] - b[2] * c[1]) / det, (a[2] * c[1] - a[1] * c[2]) / det,
             (a[1] * b[2] - a[2] * b[1]) / det],
            [(b[2] * c[0] - b[0] * c[2]) / det, (a[0] * c[2] - a[2] * c[0]) / det,
             (a[2] * b[0] - a[0] * b[2]) / det],
            [(b[0] * c[1] - b[1] * c[0]) / det, (a[1] * c[0] - a[0] * c[1]) / det,
             (a[0] * b[1] - a[1] * b[0]) / det]]


def last_F(d):
    fh = op(f"{d}/OSZICAR")
    if not fh:
        return None
    F = None
    try:
        for line in fh:
            if " F= " in line:
                t = line.split()
                try:
                    F = float(t[t.index("F=") + 1])
                except (ValueError, IndexError):
                    pass
    finally:
        fh.close()
    return F


def outcar_bits(d):
    """NELECT, per-species ZVAL, and the per-atom core electrostatic potentials (ICORELEVEL=0).

    The core-potential block is what Kumagai-Oba aligns on; it is far more robust than a planar
    LOCPOT average because it samples the potential AT the atoms, where the far region is
    unambiguous."""
    fh = op(f"{d}/OUTCAR")
    if not fh:
        return {}
    ne, zv, pot = None, [], []
    grab = 0
    try:
        for line in fh:
            if ne is None and "NELECT" in line:
                m = re.search(r"NELECT\s*=\s*([-\d.]+)", line)
                if m:
                    ne = float(m.group(1))
            if "ZVAL   =" in line:
                zv += [float(x) for x in re.findall(r"ZVAL\s*=\s*([\d.]+)", line)]
            if "average (electrostatic) potential at core" in line:
                grab = 1
                pot = []
                continue
            if grab:
                if "the test charge radii" in line or "the norm of the test charge" in line:
                    continue
                nums = re.findall(r"\d+\s+(-?\d+\.\d+)", line)
                if nums:
                    pot += [float(x) for x in nums]
                elif pot:
                    grab = 0
    finally:
        fh.close()
    return {"nelect": ne, "zval": zv, "corepot": pot}


def mic(fa, fb, cell):
    """minimum-image distance between two fractional coordinates, in Angstrom"""
    d = [fa[i] - fb[i] for i in range(3)]
    d = [x - round(x) for x in d]
    v = [sum(d[k] * cell[k][j] for k in range(3)) for j in range(3)]
    return math.sqrt(sum(x * x for x in v))


def host_ratio(name):
    out = {}
    for el, num in re.findall(r"([A-Z][a-z]?)([0-9]*\.?[0-9]*)", name.split("_")[0]):
        if el:
            out[el] = out.get(el, 0.0) + (float(num) if num else 1.0)
    return out


def eps_for(host):
    """eps_static for a host, with provenance. Alloys interpolate between binary parents."""
    if host in EPS:
        v, kind, src = EPS[host]
        return v, kind, src
    r = host_ratio(host)
    cations = [e for e in r if e in ("Cd", "Zn")]
    anions = [e for e in r if e in ("S", "Se", "Te")]
    if len(cations) >= 1 and len(anions) >= 1:
        parts, wtot, acc = [], 0.0, 0.0
        for c in cations:
            for a in anions:
                b = f"{c}{a}"
                if b not in EPS:
                    return None, None, f"no sourced eps for parent {b}"
                w = r[c] * r[a]
                acc += w * EPS[b][0]
                wtot += w
                parts.append(f"{b}:{EPS[b][0]}")
        if wtot:
            return (round(acc / wtot, 3), "vegard",
                    "Vegard interpolation over " + ", ".join(parts))
    return None, None, "no sourced eps"


# ---------------------------------------------------------------------------------------------
print("Ewald gate:")
g = gates()
if not g["pass"]:
    sys.exit("Ewald gates FAILED -- refusing to compute any correction")

CHEMPOT = {}
for f in glob.glob(f"{LOG}/chempot_*.json"):
    th = os.path.basename(f)[len("chempot_"):-len(".json")]
    if th.endswith("_only"):
        continue
    try:
        CHEMPOT[th] = json.load(open(f))
    except Exception:
        pass
print(f"chempot theories loaded: {sorted(CHEMPOT)}")

VBM_BY_PATH, VBM_BY_E = {}, {}
for f in glob.glob(f"{LOG}/phys_bulk_*.jsonl"):
    for line in open(f):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("vbm") is None:
            continue
        if r.get("path"):
            VBM_BY_PATH[r["path"]] = r["vbm"]
        # also key on (theory, total energy): directories have been renamed since extraction,
        # so a path lookup alone silently loses the band edge and q*(E_VBM + E_F) goes missing
        if r.get("theory") is not None and r.get("F") is not None:
            VBM_BY_E[(r["theory"], round(r["F"], 4))] = (r["vbm"], r.get("cbm"), r.get("gap"))
print(f"band edges indexed for {len(VBM_BY_PATH)} paths / {len(VBM_BY_E)} energies")

DEF = f"{B}/DFT/defect"
targets = []
for th in sorted(os.listdir(DEF)):
    if not os.path.isdir(f"{DEF}/{th}"):
        continue
    for host in sorted(os.listdir(f"{DEF}/{th}")):
        if os.path.isdir(f"{DEF}/{th}/{host}"):
            targets.append((th, host))
if ONLY:
    t, h = ONLY.split("/")
    targets = [(t, h)]
print(f"{len(targets)} (theory, host) targets\n")

out, stats = [], collections.Counter()
for th, host in targets:
    hd = f"{DEF}/{th}/{host}"
    defects = [d for d in sorted(os.listdir(hd)) if os.path.isdir(f"{hd}/{d}")]
    if not defects:
        continue
    # a representative defect cell fixes the lattice the pristine must match
    ref_cell = None
    for d in defects:
        subs = [c for c in sorted(os.listdir(f"{hd}/{d}")) if os.path.isdir(f"{hd}/{d}/{c}")]
        if subs:
            p = poscar(f"{hd}/{d}/{subs[0]}")
            if p:
                ref_cell = p["cell"]
                break
    if ref_cell is None:
        stats["no_defect_cell"] += 1
        continue
    ref_abc = [math.sqrt(sum(x * x for x in v)) for v in ref_cell]

    # --- pristine: the bulk run whose lattice matches (gate 2) --------------------------------
    broot = f"{B}/DFT/bulk/{th}"
    cands = []
    if os.path.isdir(broot):
        for name in os.listdir(broot):
            if host not in name and name.split("_")[0] != host.split("_")[0]:
                continue
            base = f"{broot}/{name}"
            paths = [base]
            if os.path.isdir(base):
                paths += [f"{base}/{s}" for s in os.listdir(base)
                          if os.path.isdir(f"{base}/{s}")]
            for pth in paths:
                pp = poscar(pth)
                if not pp:
                    continue
                abc = [math.sqrt(sum(x * x for x in v)) for v in pp["cell"]]
                if max(abs(a - b) for a, b in zip(abc, ref_abc)) < 0.01:
                    F = last_F(pth)
                    if F is not None:
                        cands.append((pth, pp, F))
    if not cands:
        stats["no_cell_matched_pristine"] += 1
        out.append({"theory": th, "host": host, "blocked": "no cell-matched pristine reference"})
        continue
    ppath, pdata, E_pristine = sorted(cands)[0]
    pbits = outcar_bits(ppath)

    alpha_M, L, V = madelung(pdata["cell"])
    eps, eps_kind, eps_src = eps_for(host)

    # host VBM from the extraction records for this same run
    # host VBM: from the SAME pristine supercell run whose energy is the reference, so the
    # reservoir term q(E_VBM + E_F) and the energy term share one calculation
    vbm = VBM_BY_PATH.get(ppath.replace(B + "/", ""))
    gap = cbm = None
    hit = VBM_BY_E.get((th, round(E_pristine, 4)))
    if hit:
        if vbm is None:
            vbm = hit[0]
        cbm, gap = hit[1], hit[2]

    hostrec = {"theory": th, "host": host,
               "pristine": {"path": ppath.replace(B + "/", ""), "E": E_pristine,
                            "comp": pdata["comp"], "natoms": pdata["natoms"],
                            "a": round(ref_abc[0], 4)},
               "alpha_M": round(alpha_M, 6), "L_ang": round(L, 4), "volume": round(V, 3),
               "eps_static": eps, "eps_kind": eps_kind, "eps_source": eps_src,
               "vbm": vbm, "cbm": cbm, "gap": gap, "defects": {}}

    for dname in defects:
        dp = f"{hd}/{dname}"
        charges = [c for c in sorted(os.listdir(dp)) if os.path.isdir(f"{dp}/{c}")]
        # The alignment reference is this defect's OWN NEUTRAL cell, not the pristine.
        # The pristine bulk run was written with ICORELEVEL=1 and carries no core-potential
        # table, while every defect run has one (ICORELEVEL=0, set for exactly this purpose).
        # Charged-vs-neutral is also the cleaner comparison: identical cell, identical atom
        # ordering, so the potentials subtract atom-for-atom with no image matching at all, and
        # it isolates precisely what the correction targets -- the offset introduced by the
        # compensating background, which the neutral cell does not carry.
        neut = outcar_bits(f"{dp}/Neutral") if os.path.isdir(f"{dp}/Neutral") else {}
        neut_pos = poscar(f"{dp}/Neutral") if os.path.isdir(f"{dp}/Neutral") else None
        rec = {"charges": {}, "align_ref": "own neutral cell"}
        for cname in charges:
            cd = f"{dp}/{cname}"
            pdc = poscar(cd)
            E = last_F(cd)
            if not pdc or E is None:
                continue
            dn = {e: pdc["comp"].get(e, 0) - pdata["comp"].get(e, 0)
                  for e in set(pdc["comp"]) | set(pdata["comp"])}
            dn = {e: v for e, v in dn.items() if v}
            q = 0 if cname == "Neutral" else int(cname.replace("Charged", ""))
            bits = outcar_bits(cd)
            # gate 3: the electron count must equal sum(ZVAL) - q, with the ZVALs read from
            # THIS run's own OUTCAR so extrinsic species are covered too
            qcheck = None
            if bits.get("nelect") is not None and bits.get("zval"):
                order = list(pdc["comp"])
                if len(bits["zval"]) >= len(order):
                    z = dict(zip(order, bits["zval"]))
                    n0 = sum(pdc["comp"][e] * z[e] for e in order)
                    qcheck = round(n0 - bits["nelect"], 3)

            # --- alignment: this charge state against its own neutral, far region ----------
            dV = dV_sd = n_far = None
            site = None
            if q and bits.get("corepot") and neut.get("corepot") and neut_pos and \
               len(bits["corepot"]) == pdc["natoms"] and \
               len(neut["corepot"]) == neut_pos["natoms"] and \
               pdc["natoms"] == neut_pos["natoms"] and \
               pdc["species"] == neut_pos["species"]:
                # defect centre: the introduced atom where there is one, else the vacated site
                added = [e for e, v in dn.items() if v > 0]
                removed = [e for e, v in dn.items() if v < 0]
                if added:
                    idx = [i for i, sp in enumerate(pdc["species"]) if sp == added[0]]
                    if idx:
                        site = pdc["coords"][idx[-1]]
                if site is None and removed:
                    for i, sp in enumerate(pdata["species"]):
                        if sp != removed[0]:
                            continue
                        near = min((mic(pdc["coords"][j], pdata["coords"][i], pdata["cell"])
                                    for j, s2 in enumerate(pdc["species"]) if s2 == sp),
                                   default=9e9)
                        if near > 1.0:
                            site = pdata["coords"][i]
                            break
                if site is not None:
                    rcut = 0.35 * min(ref_abc)
                    diffs = []
                    for j, fj in enumerate(pdc["coords"]):
                        if mic(fj, site, pdc["cell"]) < rcut:
                            continue
                        diffs.append(bits["corepot"][j] - neut["corepot"][j])
                    if len(diffs) >= 8:
                        dV = sum(diffs) / len(diffs)
                        dV_sd = math.sqrt(sum((x - dV) ** 2 for x in diffs) / (len(diffs) - 1))
                        n_far = len(diffs)

            # Makov-Payne image term, and the Lany-Zunger screened variant. J1 calls LZ optional
            # and requires the choice to be stated; both are carried so a consumer can see the
            # spread rather than inherit an unlabelled convention.
            E_lat = E_lat_lz = None
            if q and eps:
                E_lat = q * q * alpha_M * HARTREE_ANG / (2.0 * eps * L)
                E_lat_lz = E_lat * (1.0 - (1.0 / 3.0) * (1.0 - 1.0 / eps))
            E_corr = E_corr_lz = None
            if q == 0:
                E_corr = E_corr_lz = 0.0
            elif E_lat is not None and dV is not None:
                E_corr = E_lat - q * dV
                E_corr_lz = E_lat_lz - q * dV

            rec["charges"][cname] = {
                "q": q, "E": E, "dE": round(E - E_pristine, 6), "dn": dn,
                "nelect": bits.get("nelect"), "q_from_nelect": qcheck,
                "q_consistent": (qcheck is None or abs(qcheck - q) < 1e-3),
                "E_lattice": None if E_lat is None else round(E_lat, 5),
                "E_lattice_LZ": None if E_lat_lz is None else round(E_lat_lz, 5),
                "E_corr_LZ": None if E_corr_lz is None else round(E_corr_lz, 5),
                "dV_align": None if dV is None else round(dV, 5),
                "dV_sd": None if dV_sd is None else round(dV_sd, 5),
                "dV_n_atoms": n_far,
                "E_corr": None if E_corr is None else round(E_corr, 5),
                "corr_scheme": ("Makov-Payne image + core-potential alignment"
                                if E_corr not in (None, 0.0) else
                                ("none needed (q=0)" if q == 0 else "BLOCKED")),
            }
            stats["charge_states"] += 1
            if E_corr is None and q:
                stats["corr_blocked"] += 1
            if qcheck is not None and abs(qcheck - q) > 1e-3:
                stats["q_mismatch"] += 1
        if rec["charges"]:
            hostrec["defects"][dname] = rec
    out.append(hostrec)
    stats["hosts"] += 1

json.dump(out, open(f"{LOG}/defect_ef_raw.json", "w"), indent=1)
print(f"\nwrote {LOG}/defect_ef_raw.json")
print("stats:", dict(stats))
