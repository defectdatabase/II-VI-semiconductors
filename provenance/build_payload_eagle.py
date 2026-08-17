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
import os, re, io, json, glob, gzip, math, time, tarfile, collections, gc

B    = "/eagle/wbg_defects/materialsHUB/telluride"
LOG  = f"{B}/log"
OUT  = f"{LOG}/payload"
os.makedirs(OUT, exist_ok=True)

# Eagle is Lustre: creating 56k small files runs at about 70 a minute, which is seven hours for
# this payload. The same members written into a sequential tar take a couple of minutes, and the
# site unpacks them into docs/dos and docs/runs on the Mac.
class TarOut:
    def __init__(self, path, prefix):
        self.tf = tarfile.open(path, "w")
        self.prefix = prefix
        self.n = 0

    def add(self, name, obj):
        raw = json.dumps(obj, separators=(",", ":")).encode()
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
            g.write(raw)
        data = buf.getvalue()
        ti = tarfile.TarInfo(f"{self.prefix}/{name}.json.gz")
        ti.size = len(data)
        ti.mtime = 0
        self.tf.addfile(ti, io.BytesIO(data))
        self.n += 1

    def close(self):
        self.tf.close()


dos_tar = TarOut(f"{OUT}/dos.tar", "dos")
run_tar = TarOut(f"{OUT}/runs.tar", "runs")

# Kept in step with build_bulk_payload.py: this map missing PBE+U is why every PBE+U row on the
# site had no INCAR to show -- the run breakdown was never written for a theory the map denied.
THEORY = {"PBE": "PBE", "PBEsol": "PBEsol", "HSE": "HSE06", "HSE+SOC": "HSE+SOC",
          "PBE+U": "PBE+U", "HSE+U": "HSE+U", "PBEsol+U": "PBEsol+U"}
FK     = {"PBE": "pbe", "PBEsol": "pbesol", "HSE06": "hse", "HSE+SOC": "hse_soc",
          "PBE+U": "pbe_u", "HSE+U": "hse_u", "PBEsol+U": "pbesol_u"}
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
    # Anything that is not PBEsol/HSE06/HSE+SOC used to be written as pbe__<name>, so a PBE+U
    # run and a PBE run of the same compound COLLIDED on one key and the last written won: the
    # PBE card for ZnIn2S4 served an INCAR with LDAU = .TRUE., and the PBE+U row had no key at
    # all. FK is the template's own map, so pbe_u__ / hse_u__ come out distinct.
    return f"{FK.get(theory, 'pbe')}__{name}_{ord_}"


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
dos, n_dos_rec = index_jsonl("dos_bulk_*.jsonl")
print(f"steps records {n_steps_rec}  dos records {n_dos_rec}")


def stream_defect_dos(charge_label_to_q):
    """dos_defect_*.jsonl keyed by (theory, host, defect, charge label). PBE+PBEsol alone are
    ~770 MB combined -- an earlier version parsed every matching line into a dict held for the
    rest of the run (up to ~9,700 full element-projected arrays) and the build was silently
    SIGKILLed by the login node's OOM guard, with zero traceback since a kill -9 gives Python no
    chance to run its exception handling at all -- the log file stayed genuinely empty even on a
    completed process. Streaming straight into dos_tar and keeping only the small string keys
    (not the arrays) afterward is the fix; nothing this big should ever sit fully in memory.
    Returns {(theory,host,defect,q): dos_key} -- q already resolved to the numeric string."""
    out, n = {}, 0
    # PBE (490 MB) and PBEsol (283 MB) defect DOS files push this login node's ~5.3 GB memory
    # ceiling over the edge even streaming line by line (confirmed: two runs both SIGKILLed,
    # status 137, at the same RSS regardless of whether matched records were cached or written
    # immediately -- the memory pressure is in parsing the huge files themselves, not what is
    # kept afterward). HSE/HSE+SOC together are under 25 MB and safe. PBE/PBEsol defect DOS is
    # deferred to a PBS job with dedicated node memory once the queue (20/20 queued) drains.
    for f in sorted(glob.glob(f"{LOG}/dos_defect_*.jsonl")):
        for line in open(f):
            try:
                r = json.loads(line)
            except Exception:
                continue
            theory, host, defect, cname = r.get("theory"), r.get("host"), r.get("defect"), r.get("charge")
            q = charge_label_to_q.get((theory, host, defect, cname))
            if q is None:
                continue
            fk = FK.get(THEORY.get(theory, theory), theory)
            defect_pub = rename_old2new.get((theory, host, defect), defect)
            dk = f"{fk}__{host}__{defect_pub}__{q}"
            dos_tar.add(dk, {"ef": r.get("ef"), "e": r.get("e"), "total": r.get("total"),
                             "el": r.get("el") or {}, "projected": bool(r.get("projected"))})
            out[(theory, host, defect_pub, q)] = dk
            n += 1
    return out, n


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

# ---------------- SLME (Yu-Zunger), ASTM G173-03 AM1.5G global tilt ----------------
import math as _m
def _load_am15(path):
    E, phi = [], []          # photon energy (eV, ascending), photon flux per eV (m-2 s-1 eV-1)
    rows = []
    for line in open(path):
        p = line.strip().split(",")
        try:
            lam, g = float(p[0]), float(p[2])
        except (ValueError, IndexError):
            continue
        rows.append((lam, g))
    HC = 1239.84193          # eV*nm
    Q = 1.602176634e-19
    for lam, g in rows:
        e = HC / lam                       # eV
        # W m-2 nm-1 -> photons m-2 s-1 nm-1 -> per eV: multiply |dlam/dE| = HC/E^2
        phot_per_nm = g * lam * 1e-9 / (Q * e * 1e-9) if e > 0 else 0.0
        phi.append((e, g / (Q * e) * (HC / e**2)))
    phi.sort()
    return [x[0] for x in phi], [x[1] for x in phi]
_AM15_E, _AM15_PHI = _load_am15(f"{LOG}/astmg173.csv")
_PIN = 0.0
for _i in range(1, len(_AM15_E)):
    de = _AM15_E[_i] - _AM15_E[_i-1]
    _PIN += 0.5*(_AM15_E[_i]*_AM15_PHI[_i] + _AM15_E[_i-1]*_AM15_PHI[_i-1]) * de * 1.602176634e-19
def slme_500nm(abs_pairs, gap):
    """Yu-Zunger SLME at L = 500 nm, T = 300 K, radiative recombination only (fr = 1; the
    indirect-gap penalty needs the direct-allowed gap, which the campaign did not archive)."""
    if not abs_pairs or gap is None or gap < 0.31:
        return None
    Es  = [p[0] for p in abs_pairs]
    als = [p[1] for p in abs_pairs]
    if max(als) <= 0:
        return None
    L = 500e-7                                  # cm
    kT = 0.025852
    q = 1.602176634e-19
    def alpha_at(e):
        # DFT spectra carry smeared sub-gap tails; blackbody flux diverges at low E, so a tail
        # of a few 1e3 cm-1 collapsed Voc and published 2-6% for 30% materials. SLME uses the
        # gap as the absorption onset.
        if e < gap: return 0.0
        if e <= Es[0]: return 0.0
        if e >= Es[-1]: return als[-1]
        lo, hi = 0, len(Es)-1
        while hi-lo > 1:
            mid=(lo+hi)//2
            if Es[mid] <= e: lo=mid
            else: hi=mid
        t=(e-Es[lo])/(Es[hi]-Es[lo])
        return als[lo]+t*(als[hi]-als[lo])
    Jsc = 0.0
    for i in range(1, len(_AM15_E)):
        e0,e1=_AM15_E[i-1],_AM15_E[i]
        if e1 < gap: continue
        a0=1.0-_m.exp(-2.0*alpha_at(e0)*L); a1=1.0-_m.exp(-2.0*alpha_at(e1)*L)
        Jsc += 0.5*(a0*_AM15_PHI[i-1]+a1*_AM15_PHI[i])*(e1-e0)
    Jsc *= q
    # J0 from the 300 K blackbody through the same absorptivity
    J0 = 0.0
    C = 2*_m.pi/( (4.135667696e-15)**3 * (2.99792458e10)**2 )   # h in eV*s, c in cm/s -> cm-2 s-1 eV-3
    e = gap
    while e < 5.0:
        de = 0.005
        a = 1.0-_m.exp(-2.0*alpha_at(e)*L)
        J0 += a * C*e*e/_m.expm1(e/kT) * de
        e += de
    J0 *= q * 1e4                              # cm-2 -> m-2
    if J0 <= 0 or Jsc <= 0:
        return None
    best = 0.0
    V = 0.0
    Voc = kT*_m.log(Jsc/J0+1.0)
    while V < Voc:
        Jv = Jsc - J0*_m.expm1(V/kT)
        if Jv <= 0: break
        best = max(best, Jv*V)
        V += 0.005
    return round(100.0*best/_PIN, 2)


_FU_CACHE = {}
def fu_lookup(theory, name):
    k = (theory, name)
    if k in _FU_CACHE: return _FU_CACHE[k]
    row2 = None
    for kk, rr in bulk.items():
        if rr.get("theory") == theory and rr.get("compound") == name:
            row2 = rr; break
    if row2 and row2.get("composition"):
        comp = row2["composition"]
        vals = list(comp.values())
        g = 0
        ints = all(float(v).is_integer() for v in vals)
        if ints:
            for v in vals: g = _m.gcd(g, int(v))
        g = g or 1
        out = {"atoms": sum(vals) / g}
    elif re.fullmatch(r"[A-Z][a-z]?", name):
        out = {"atoms": 1}
    else:
        m2 = re.findall(r"([A-Z][a-z]?)([0-9.]*)", re.sub(r"_(kesterite|stannite|reference)$", "", name))
        out = {"atoms": sum(float(n2) if n2 else 1.0 for _, n2 in m2) or 1}
    _FU_CACHE[k] = out
    return out

def run_mode(incar_text):
    if isinstance(incar_text, (list, tuple)):
        incar_text = "\n".join(map(str, incar_text))
    if isinstance(incar_text, dict):
        incar_text = "\n".join(f"{k} = {v}" for k, v in incar_text.items())
    if not incar_text or not isinstance(incar_text, str):
        return None
    def gv(tag, default):
        m = re.search(rf"{tag}\s*=\s*(-?\d+)", incar_text)
        return int(m.group(1)) if m else default
    nsw, ibrion, isif = gv("NSW", 0), gv("IBRION", -1), gv("ISIF", 2)
    if ibrion == 0:
        return "md"
    if nsw <= 0 or ibrion == -1:
        return "static"
    return "relax-cell" if isif >= 3 else "relax-ions"

byname = collections.defaultdict(dict)         # (theory, name) -> {ord: row}
dos_keys, run_keys = [], []
n_dos = n_runs = 0
t0 = time.time()

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
    eps_avg = r.get("eps_avg")
    if r.get("eps_xx") is not None:
        eps3 = [round(r["eps_xx"], 4), round(r["eps_yy"], 4), round(r["eps_zz"], 4)]
    # a dielectric constant <= 0 (or absurdly large) is a failed/unconverged DFPT run, not a
    # material property: publish nothing rather than a nonsense number
    if (eps_avg is not None and not (0 < eps_avg < 1000)) or (eps3 and any(not (0 < x < 1000) for x in eps3)):
        eps3, eps_avg = None, None
    slme = None
    if r.get("abs_E") and r.get("abs_alpha") and r.get("gap"):
        try: slme = slme_500nm(list(zip(r["abs_E"], r["abs_alpha"])), r.get("gap"))
        except Exception: slme = None
    # decomposition, term by term, in per-f.u. formation enthalpies (exactly consistent with
    # the published number: edec_fu = dHf_fu(host) - sum coeff * dHf_fu(phase))
    dterms = None
    if edec_fu is not None and r.get("decomp_terms"):
        A = r["natoms"] / nfu
        tl = []
        oksum = 0.0
        for t in r["decomp_terms"]:
            if t.get("w", 0) <= 1e-9:
                continue   # zero-weight member of the tie-line: not part of the decomposition
            pc = fu_lookup(r["theory"], t["name"])
            coeff = t["w"] * A / pc["atoms"]
            E_pfu = t["dH_pa"] * pc["atoms"]
            tl.append({"coeff": round(coeff, 4), "phase": t["name"],
                       "E_pfu": round(E_pfu, 4), "contribution": round(coeff*E_pfu, 4)})
            oksum += coeff*E_pfu
        host_dHf_fu = r["Ef_per_atom"] * A if r.get("Ef_per_atom") is not None else None
        if host_dHf_fu is not None:
            dterms = {"kind": "stoichiometric mix", "E_pfu": round(host_dHf_fu, 4),
                      "pre": 1, "sum": round(oksum, 4), "S": 0.0,
                      "d0": round(host_dHf_fu - oksum, 4), "terms": tl}

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
        None, None, None, None,                                 # 23-26 reserved
        dterms,                                                 # 27 decomposition, term by term
        st.get("n_steps") if st else None,                      # 28 ionic steps taken
        run_mode(st.get("incar")) if st else None,              # 29 what the INCAR asked for
        (st.get("force_converged") if st.get("force_converged") is not None
         else st.get("reached_required_accuracy")) if st else None,   # 30 converged?
    ]
    row[3] = eps_avg
    row[4] = slme
    row[13] = eps3
    row[14] = [[0.5, slme]] if slme is not None else None   # thickness curve shape (um, %)
    byname[(theory, name)][poly] = row

    sk = struct_key(name, theory, poly)
    if dr:
        dos_tar.add(sk, {"ef": dr.get("ef"), "e": dr.get("e"), "total": dr.get("total"),
                         "el": dr.get("el") or {}, "projected": bool(dr.get("projected"))})
        dos_keys.append(sk)
        n_dos += 1
    if st:
        run_tar.add(sk, {"F": st.get("F"), "kmesh": st.get("kmesh"), "potcar": st.get("potcar"),
                         "incar": st.get("incar"), "ediffg": st.get("ediffg"),
                         "n_steps": st.get("n_steps"), "steps": st.get("steps"),
                         "force_converged": st.get("force_converged"),
                         "reached_required_accuracy": st.get("reached_required_accuracy")})
        run_keys.append(sk)
        n_runs += 1
    if r.get("abs_E") and r.get("abs_alpha"):
        # alpha(E) as [E, alpha] pairs, which is the shape the detail panel already reads
        optics[sk] = {"abs": [[e, a] for e, a in zip(r["abs_E"], r["abs_alpha"])],
                      "slme": ([[0.5, slme]] if slme is not None else None),
                      "eps": eps3, "source": r.get("alpha_source")}

print(f"tars written in {time.time() - t0:.0f}s")

for (theory, name), ords in sorted(byname.items()):
    # the published polymorph is the most stable one that HAS a formation energy
    scored = [(o, v) for o, v in ords.items() if v[0] is not None]
    best = min(scored, key=lambda t: t[1][0])[0] if scored else sorted(ords)[0]
    rec = {"n": name, "f": theory, "o": ords, "b": best}
    if theory == "HSE06":
        rec["rk"] = "HSE06 (A2BCX4)"
    compounds.append(rec)

print(f"compounds {len(compounds)}  dos files {n_dos}  run files {n_runs}  optics {len(optics)}")

# The bulk dos/steps indexes hold one full JSON record (a ~300-point array per element) for
# EVERY bulk DOS/steps line ever read -- several GB by themselves. The defects section does not
# need them, and this login node kills anything crossing ~5 GB RSS with a bare SIGKILL (status
# 137, no traceback possible) -- confirmed by watching RSS climb to 5.27 GB right before an
# unpatched run died silently. Dropping them here is what buys the defect DOS streaming its room.
del dos, steps
gc.collect()

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

# small: (theory,host,defect,charge label) -> numeric q string. No arrays, just the map needed
# to resolve the DOS scan's charge LABEL (e.g. "Charged-1") to the numeric q used everywhere else.
charge_label_to_q = {}
for r in dd:
    for v in (r.get("vertices") or {}).values():
        for cname, c in (v.get("charges") or {}).items():
            charge_label_to_q[(r["theory"], r["host"], r["defect"], cname)] = str(c["q"])
            if r.get("archived_as"):
                charge_label_to_q[(r["theory"], r["host"], r["archived_as"], cname)] = str(c["q"])

rename_old2new = {(r["theory"], r["host"], r["archived_as"]): r["defect"]
                  for r in dd if r.get("archived_as")}

dos_by_key, n_dos_defect = stream_defect_dos(charge_label_to_q)
dos_keys.extend(dos_by_key.values())
print(f"defect dos matched {n_dos_defect}")

defects = []
for r in dd:
    theory = THEORY.get(r["theory"], r["theory"])
    fk = FK.get(theory, theory)
    vx = {}
    e = {}
    corr = {}
    dos_by_q = {}
    for vname, v in (r.get("vertices") or {}).items():
        ch = {}
        for cname, c in (v.get("charges") or {}).items():
            q = str(c["q"])
            ch[q] = {"dE": c.get("dE"), "vbm": c.get("Ef_VBM"), "cbm": c.get("Ef_CBM"),
                     "note": c.get("note"),
                     # every term behind Ef, so the panel can show the arithmetic instead of
                     # asking the reader to trust a single collapsed number
                     "E": c.get("E"), "Ebulk": c.get("Ebulk"),
                     "musum": c.get("musum"), "muterms": c.get("muterms"), "mu": c.get("mu")}
            if c.get("dE") is not None and q not in e:
                e[q] = c["dE"]
            if q not in corr:
                corr[q] = bool(c.get("corrected"))
            dk = dos_by_key.get((r["theory"], r["host"], r["defect"], q))
            if dk is not None:
                dos_by_q[q] = dk
        vx[vname] = {"facet": v.get("facet") or [], "q": ch,
                     "dmu": v.get("dmu"), "eqs": v.get("eqs")}
    # a vertex is USABLE for the Ef(E_F) plot only if it actually solved (has vbm/cbm, not just
    # the elemental-rich fallback that ships dE with vbm/cbm left null)
    usable = [vn for vn, v in vx.items()
              if any(c.get("vbm") is not None for c in v["q"].values())]
    defects.append({
        "f": fk, "h": r["host"], "d": r["defect"],
        "t": r.get("host_bulk_match", "raw"),
        "g": r.get("host_gap"), "v": r.get("host_vbm"),
        "hF": r.get("host_F"), "hN": r.get("host_natoms"), "hpa": r.get("host_F_per_atom"),
        "nps": r.get("n_pristine"), "cm": r.get("dn_commensurate"),
        "aa": r.get("archived_as"), "ceq": r.get("chem_eq"),
        "e": e, "corr": corr, "dos": dos_by_q,
        "src": f"raw ({r.get('host_bulk_match')})",
        "u": None, "rq": None,
        "dn": r.get("dn"), "nat": r.get("natoms"),
        "nc": r.get("n_configs"), "sp": r.get("config_spread_meV"),
        "vx": vx, "vxu": usable, "tl": r.get("transition_levels") or [],
        "gs": r.get("ground_state"),
    })
print(f"defects {len(defects)}  ({sum(1 for d in defects if d['vxu'])} with a resolved chem-pot vertex,"
      f" {n_dos_defect} with element-projected DOS)")
dos_tar.close()
run_tar.close()

# ---------------------------------------------------------------- refs from the chem-pot build
cp = json.load(open(f"{LOG}/chempot.json"))
refs = {}
for th, o in cp.items():
    refs[THEORY.get(th, th)] = {"el": o.get("mu0", {}), "bin": {}}

# gen_traj.py (bulk) and gen_traj_defect.py (defect) run separately and write sharded
# trajkeys_*.json / dtrajkeys_*.json -- merge them here so "trajKeys: []" never ships again
# and the "Relaxation movie" button silently vanishes from every row.
traj_keys = set()
for pattern in ("trajkeys_*.json", "dtrajkeys_*.json"):
    for shard in glob.glob(f"{OUT}/{pattern}"):
        traj_keys.update(json.load(open(shard)))

data = {
    "defects": defects,
    "compounds": compounds,
    "refs": refs,
    "structKeys": sorted(struct_key(n, t, o) for (t, n), ords in byname.items() for o in ords),
    "trajKeys": sorted(traj_keys),
    "dosKeys": sorted(dos_keys),
    "runKeys": sorted(run_keys),
}
with open(f"{OUT}/data.json", "w") as fh:
    json.dump(data, fh, separators=(",", ":"))
with gzip.open(f"{OUT}/optics.json.gz", "wt") as fh:
    json.dump(optics, fh, separators=(",", ":"))
with gzip.open(f"{OUT}/chempot.json.gz", "wt") as fh:
    json.dump(cp, fh, separators=(",", ":"))

print("wrote", OUT)
for f in ("data.json", "optics.json.gz", "chempot.json.gz", "dos.tar", "runs.tar"):
    print(f"  {f} {os.path.getsize(f'{OUT}/{f}'):,} bytes")
print(f"  dos {len(data['dosKeys'])} members   runs {len(data['runKeys'])} members")
