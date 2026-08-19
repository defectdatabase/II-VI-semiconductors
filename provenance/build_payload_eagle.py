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


# ---------------------------------------------------------------- run footing (the INCAR is the truth)
# The theory label on a row comes from the directory tree; the archived INCAR is what actually ran.
# Audit 2026-08-17 over every bulk run record: 55 "PBEsol"-labelled runs are HSE, 39 "HSE" runs
# are PBEsol, and the HSE tree itself mixes HSE06 (PBE base, mostly ENCUT 400) with HSEsol
# (PBEsol base) whose total energies sit ~0.2 eV/atom apart; build_all took the lowest-energy
# variant per compound AND per element regardless of footing, which is how Na2Sr1Sn1Te4 got a
# +2252 eV/f.u. decomposition energy, Na2Cd1Sn1Se4 -116, and the CdSeTe alloys +85..+106.
# Every energetic quantity below (formation energy, decomposition) is therefore re-derived here
# from run records of ONE footing class -- functional, hybrid base, SOC, +U -- against elemental
# references of that same class computed with the same PAW potential; a row whose published energy
# cannot be traced to a run of its own class is withheld and says why.
def foot_of(inc):
    if isinstance(inc, (list, tuple)): inc = "\n".join(map(str, inc))
    if isinstance(inc, dict): inc = " ".join(f"{a}={v}" for a, v in inc.items())
    inc = inc or ""
    def g(t):
        m = re.search(rf"\b{t}\s*=\s*([^\s;]+)", inc, re.I)
        return m.group(1) if m else None
    T = lambda v: bool(v) and v.strip(".").upper().startswith("T")
    hf, soc, u = T(g("LHFCALC")), T(g("LSORBIT")), T(g("LDAU"))
    gga = (g("GGA") or "").upper()
    base = "PBEsol" if gga == "PS" else ("PBE" if gga in ("", "PE") else gga)
    if g("METAGGA"): base = g("METAGGA").upper()
    f = ("HSE/" + base) if hf else base
    if soc: f += "+SOC"
    if u: f += "+U"
    return f, g("ENCUT")

LABEL_CLASSES = {"PBE": ("PBE",), "PBE+U": ("PBE+U",), "PBEsol": ("PBEsol",), "PBEsol+U": ("PBEsol+U",),
                 "HSE": ("HSE/PBEsol", "HSE/PBE"), "HSE+SOC": ("HSE/PBEsol+SOC", "HSE/PBE+SOC"),
                 "HSE+U": ("HSE/PBE+U", "HSE/PBEsol+U")}
CLASS_LABEL = {"PBE": "PBE", "PBEsol": "PBEsol", "PBE+U": "PBE+U", "PBEsol+U": "PBEsol+U",
               "HSE/PBE": "HSE06 (PBE base)", "HSE/PBEsol": "HSE06 (PBEsol base)",
               "HSE/PBEsol+SOC": "HSE+SOC (PBEsol base)", "HSE/PBE+SOC": "HSE+SOC (PBE base)",
               "HSE/PBE+U": "HSE+U (PBE base)", "HSE/PBEsol+U": "HSE+U (PBEsol base)"}
def class_label(c): return CLASS_LABEL.get(c, c)
def _potsym(p):                     # 'PAW_PBE Na_pv 19Sep2006' -> ('Na', 'Na_pv')
    parts = str(p).split()
    if len(parts) < 2: return None, None
    return parts[1].split("_")[0], parts[1]

RUNS = {}          # (theory label, compound) -> [ {F, nat, fpa, cls, enc, var, pot} ]
for (_th, _cn), _lst in steps.items():
    _seen, _out = set(), []
    for _d in _lst:
        if _d.get("F") is None: continue
        _v = _d.get("variant") or ""
        if _v in _seen: continue
        _seen.add(_v)
        _vm = re.match(r"(\d+)_atoms", _v)   # NOT _m -- that is the module's math alias, and
        _nat = int(_vm.group(1)) if _vm else None   # shadowing it silently killed every SLME call
        _cls, _enc = foot_of(_d.get("incar"))
        _Es = [s.get("E") for s in (_d.get("steps") or []) if s.get("E") is not None]
        _out.append({"F": _d["F"], "nat": _nat, "fpa": (_d["F"] / _nat if _nat else None),
                     "cls": _cls, "enc": _enc, "var": _v, "pot": list(_d.get("potcar") or []),
                     "emin": (min(_Es) if _Es else None), "nsteps": len(_Es)})
    RUNS[(_th, _cn)] = _out

EREF = {}          # cls -> PAW symbol ('Na_pv') -> {"mu", "enc", "var", "el"}
for (_th, _cn), _lst in RUNS.items():
    if not re.fullmatch(r"[A-Z][a-z]?", _cn): continue
    for _x in _lst:
        if _x["fpa"] is None or not (-20.0 < _x["fpa"] < 0.0): continue      # diverged / broken
        if _x["emin"] is not None and (_x["F"] - _x["emin"]) / _x["nat"] > 0.05: continue
        _syms = [_potsym(p)[1] for p in _x["pot"]]
        _sym = next((s for s in _syms if s and s.split("_")[0] == _cn), None)
        if not _sym: continue
        _cur = EREF.setdefault(_x["cls"], {}).get(_sym)
        if _cur is None or _x["fpa"] < _cur["mu"]:
            EREF[_x["cls"]][_sym] = {"mu": _x["fpa"], "enc": _x["enc"], "var": _x["var"], "el": _cn}
print("footing classes with elemental references:",
      {c: len(v) for c, v in sorted(EREF.items())})

def ref_lookup(cls, el, pots):
    """the elemental reference of THIS class computed with the PAW this run used for `el`"""
    table = EREF.get(cls, {})
    for p in pots:
        e, sym = _potsym(p)
        if e == el and sym in table:
            return sym, table[sym]
    # no PAW list (or PAW not run as an element): fall back to any potential of that element,
    # preferring the plain one; the note discloses which was used
    for sym in sorted(table, key=lambda s: (s != el, s)):
        if sym.split("_")[0] == el:
            return sym, table[sym]
    return None, None

def formation_pa(cls, F, nat, comp_atoms, pots):
    """F - sum n_i mu_i over N, all of one class; returns (Ef_pa, refs_used, missing)"""
    used, missing, s = {}, [], 0.0
    for el, n in comp_atoms.items():
        if n <= 0: continue
        sym, ref = ref_lookup(cls, el, pots)
        if ref is None: missing.append(el); continue
        used[el] = {"paw": sym, "mu": round(ref["mu"], 6), "encut": ref["enc"]}
        s += n * ref["mu"]
    if missing: return None, used, missing
    return (F - s) / nat, used, missing

_CLS_CACHE = {}
def classify_row(theory, r):
    k = (theory, r["compound"], r.get("F"))
    if k not in _CLS_CACHE:
        _CLS_CACHE[k] = _classify_row(theory, r)
    return dict(_CLS_CACHE[k])

def _classify_row(theory, r):
    """Trace the published ground state to a run record and its footing.
    Returns dict(cls, F, nat, enc, pots, mode, note, keep_props)."""
    allowed = LABEL_CLASSES.get(theory, (theory,))
    recs = RUNS.get((theory, r["compound"]), [])
    F, nat = r.get("F"), r.get("natoms")
    match = [x for x in recs if F is not None and abs(x["F"] - F) < 0.02]
    if match:
        x = match[0]
        # a relaxation runs downhill: a final ionic step sitting more than 50 meV/atom ABOVE the
        # run's own lowest step means the last SCF diverged (Na1Ag1Cd1Zr1Se4 HSE stannite:
        # -281.9 -> -233.5 eV in one step, forces 2.3 eV/A) -- the published energy is not a
        # converged total energy and nothing derived from it can be shown
        if x["cls"] in allowed and x["emin"] is not None and nat and (F - x["emin"]) / nat > 0.05:
            return {"cls": x["cls"], "F": F, "nat": nat, "enc": x["enc"], "pots": x["pot"] or r.get("paw") or [],
                    "mode": "diverged", "keep_props": False,
                    "note": (f"the final ionic step of the archived run ({F:.2f} eV) sits {(F - x['emin'])/nat:.2f} eV/atom "
                             f"above the run's own lowest step ({x['emin']:.2f} eV): the last SCF diverged, so this "
                             f"is not a converged total energy -- energetics and properties withheld")}
        if x["cls"] in allowed:
            return {"cls": x["cls"], "F": F, "nat": nat, "enc": x["enc"], "pots": x["pot"] or r.get("paw") or [],
                    "mode": "ok", "note": None, "keep_props": True}
        return {"cls": x["cls"], "F": F, "nat": nat, "enc": x["enc"], "pots": x["pot"],
                "mode": "mislabelled", "keep_props": False,
                "note": (f"the archived run behind this entry is {class_label(x['cls'])} (from its INCAR), "
                         f"not {THEORY.get(theory, theory)}: its numbers are withheld from this level of theory")}
    same = [x for x in recs if x["cls"] in allowed and x["nat"]]
    if same:
        x = min(same, key=lambda y: y["fpa"])
        fpa_pub = (F / nat) if (F is not None and nat) else None
        far = fpa_pub is None or abs(fpa_pub - x["fpa"]) > 0.10
        note = (f"the published ground-state energy ({fpa_pub:+.3f} eV/atom) matches no archived "
                f"{THEORY.get(theory, theory)} run; energetics are taken from the archived "
                f"{class_label(x['cls'])} run '{x['var']}' ({x['fpa']:+.3f} eV/atom)"
                if fpa_pub is not None else
                f"no published energy; energetics from the archived {class_label(x['cls'])} run '{x['var']}'")
        if far:
            note += (" -- the two differ by more than 0.1 eV/atom, i.e. the published run is a different "
                     "footing (functional/basis), so its band gap, dielectric and lattice values are withheld too")
        return {"cls": x["cls"], "F": x["F"], "nat": x["nat"], "enc": x["enc"], "pots": x["pot"],
                "mode": "realigned", "note": note, "keep_props": not far}
    if recs:
        x = recs[0]
        return {"cls": None, "F": F, "nat": nat, "enc": None, "pots": r.get("paw") or [],
                "mode": "withheld", "keep_props": False,
                "note": (f"the only archived runs for this entry are {', '.join(sorted(set(class_label(y['cls']) for y in recs)))}, "
                         f"not {THEORY.get(theory, theory)}: withheld")}
    return {"cls": None, "F": F, "nat": nat, "enc": None, "pots": r.get("paw") or [],
            "mode": "norecord", "keep_props": True,
            "note": "no archived run record (INCAR/OSZICAR) exists for this entry, so its footing cannot be verified: energetics withheld"}

# ---------------------------------------------------------------- binary decomposition (nanoHUB rule)
# Decomposition into the stoichiometric set of binaries of the same footing class (the ChalcoDB /
# nanoHUB definition): d = dH_f(host, per f.u.) - min over binary combinations of sum c*dH_f(binary)
# + k_B T sum_sublattice n sum f ln f at 298.15 K.  The minimum is a small linear programme over
# ALL same-class binaries in the host's element set (elements at dH = 0), never a hand-picked list;
# every candidate's dH_f is computed from its own run record against the same-class references.
import numpy as _np
_KBT298 = 8.617333e-5 * 298.15

VALID_ELS = set(("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn "
                 "Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce "
                 "Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Ac Th Pa U Pu").split())
def _tokens(name):
    # "-SQS" (special quasirandom structure) is a structure tag, not chemistry: left in place it
    # tokenised as S+Q+S and a phantom element "Q" entered the decomposition LP at dH = 0 and
    # blocked the row's formation energy on a missing "Q" reference
    base = re.sub(r"(-SQS|_supercell)$", "",
           re.sub(r"_(kesterite|stannite|reference|zincblende|wurtzite|rocksalt|chalcopyrite)$", "",
                  re.sub(r"-\d+$", "", name)))
    base = re.sub(r"(-SQS|_supercell)$", "", base)
    toks = [(e, float(n) if n else 1.0) for e, n in re.findall(r"([A-Z][a-z]?)([0-9.]*)", base)]
    return [(e, n) for e, n in toks if e in VALID_ELS]

def _mix_entropy(name):
    toks = _tokens(name); terms = []; i = 0
    while i < len(toks):
        if abs(toks[i][1] - round(toks[i][1])) > 1e-6:      # fractional -> mixed sublattice
            j = i; tot = 0.0
            while j < len(toks) and abs(toks[j][1] - round(toks[j][1])) > 1e-6:
                tot += toks[j][1]; j += 1
                if abs(tot - round(tot)) < 1e-6 and tot > 0: break
            grp = toks[i:j]; tot = sum(n for _, n in grp)
            if abs(tot - round(tot)) < 1e-6 and len(grp) > 1:
                fr = {e: n / tot for e, n in grp}
                sfl = sum(f * _np.log(f) for f in fr.values())
                terms.append({"sublattice": "/".join(e for e, _ in grp),
                              "sites_per_fu": round(tot, 4),
                              "fractions": {e: round(f, 4) for e, f in fr.items()},
                              "sum_f_ln_f": round(float(sfl), 6),
                              "contribution_eV": round(float(tot * _KBT298 * sfl), 6)})
            i = j
        else:
            i += 1
    return terms

def _reduced(comp):
    """{'Cd':4,'Te':4} -> (('Cd',1.0),('Te',1.0)) per formula unit"""
    vals = [v for v in comp.values() if v > 0]
    if all(abs(v - round(v)) < 1e-6 for v in vals):
        g = 0
        for v in vals: g = _np.gcd(g, int(round(v)))
        g = g or 1
        return tuple(sorted((e, v / g) for e, v in comp.items() if v > 0))
    return tuple(sorted((e, v) for e, v in comp.items() if v > 0))

# every same-class binary/elemental candidate, its dH per f.u. computed ONCE per class:
# cls -> reduced composition key -> (name, dH_fu, comp_fu, variant, theory label)
_BIN_TABLE = {}
def _bin_table(cls):
    if cls in _BIN_TABLE: return _BIN_TABLE[cls]
    best = {}
    for (th, cname), lst in RUNS.items():
        toks = _tokens(cname)
        comp = {}
        for e, n in toks: comp[e] = comp.get(e, 0.0) + n
        ce = set(comp)
        if not ce or len(ce) > 2: continue
        apfu = sum(comp.values())
        for x in lst:
            if x["cls"] != cls or not x["nat"] or x["fpa"] is None or not (-20 < x["fpa"] < 0): continue
            if x["emin"] is not None and (x["F"] - x["emin"]) / x["nat"] > 0.05: continue   # diverged last step
            nfu = x["nat"] / apfu
            if abs(nfu - round(nfu)) > 1e-6: continue
            comp_atoms = {e: n * nfu for e, n in comp.items()}
            ef_pa, used, missing = formation_pa(cls, x["F"], x["nat"], comp_atoms, x["pot"])
            if ef_pa is None or abs(ef_pa) > 3.5: continue
            key = _reduced(comp)
            fu_per_key = sum(v for _, v in key)
            dH_fu = ef_pa * fu_per_key
            if key not in best or dH_fu < best[key][1]:
                best[key] = (cname, dH_fu, dict(key), x["var"], th, x["F"] / x["nat"] * fu_per_key)
    _BIN_TABLE[cls] = best
    return best

_BIN_CACHE = {}
def _binaries(cls, els):
    """same-class binary (and elemental) reference phases inside the element set, dH per f.u."""
    k = (cls, frozenset(els))
    if k in _BIN_CACHE: return _BIN_CACHE[k]
    out = [v for key, v in _bin_table(cls).items() if set(e for e, _ in key).issubset(els)]
    for e in els:                                   # elemental fallback at dH = 0
        out.append((e, 0.0, {e: 1.0}, None, None))
    _BIN_CACHE[k] = out
    return out

def _simplex_lp(cvec, A, b):
    """min c.x  s.t. A x = b, x >= 0. Two-phase tableau simplex with Bland's rule.
    Sizes here are <= 6 equations x ~25 variables. Returns x or None."""
    A = _np.asarray(A, float); b = _np.asarray(b, float); cvec = _np.asarray(cvec, float)
    m, n = A.shape
    neg = b < 0
    A[neg] *= -1; b = b.copy(); b[neg] *= -1
    T = _np.zeros((m + 1, n + m + 1))
    T[:m, :n] = A; T[:m, n:n + m] = _np.eye(m); T[:m, -1] = b
    T[m, :n] = -A.sum(axis=0); T[m, -1] = -b.sum()
    basis = list(range(n, n + m))
    def pivot(allowed):
        for _ in range(500):
            col = -1
            for j in allowed:
                if T[m, j] < -1e-10: col = j; break
            if col < 0: return True
            ratios = [(T[i, -1] / T[i, col], i) for i in range(m) if T[i, col] > 1e-10]
            if not ratios: return False
            _, row = min(ratios)
            T[row] /= T[row, col]
            for i in range(m + 1):
                if i != row and abs(T[i, col]) > 1e-12: T[i] -= T[i, col] * T[row]
            basis[row] = col
        return False
    if not pivot(list(range(n + m))) or T[m, -1] < -1e-7: return None
    T[m, :] = 0.0
    T[m, :n] = cvec
    for i, bi in enumerate(basis):
        if abs(T[m, bi]) > 1e-12: T[m] -= T[m, bi] * T[i]
    if not pivot(list(range(n))): return None
    x = _np.zeros(n + m)
    for i, bi in enumerate(basis): x[bi] = T[i, -1]
    if x[n:].max(initial=0.0) > 1e-7: return None
    return x[:n]

# ---- the ChalcoDB / paper convention (EES Solar d6el00026f, eqn for Edecomp): every cation pairs
# with every anion of the mixed anion sublattice into its valence-characteristic binary --
# A(+1) -> A2X, B(+2) -> BX, B(+3) -> B2X3, C(+4) -> CX2 -- with coefficient (n_cation/binary
# cations) x (anion fraction), plus kBT sum n f ln f. This is what the released dataset and the
# paper publish; a free LP over all binaries picked lower-energy but non-canonical sets (elements
# included), which is why the website disagreed with the paper.
_VAL1 = {"Li","Na","K","Rb","Cs","Cu","Ag"}
_VAL2 = {"Be","Mg","Ca","Sr","Ba","Zn","Cd","Hg","Mn","Fe","Ni","Co","Pb"}
_VAL3 = {"Al","Ga","In"}
_VAL4 = {"Si","Ge","Sn","Ti","Zr","Hf"}
_ANION = {"S","Se","Te","O"}
def chalcodb_decomp(cls, name, comp_fu, dHf_fu):
    cats = {e: n for e, n in comp_fu.items() if e not in _ANION and n > 0}
    ans  = {e: n for e, n in comp_fu.items() if e in _ANION and n > 0}
    if not cats or not ans:
        return None, "no cation/anion partition"
    def val(e):
        return 1 if e in _VAL1 else 2 if e in _VAL2 else 3 if e in _VAL3 else 4 if e in _VAL4 else None
    if any(val(e) is None for e in cats):
        return None, "cation outside the ABX2/A2BCX4 valence classes"
    nX = sum(ans.values())
    if abs(sum(val(e) * n for e, n in cats.items()) - 2.0 * nX) > 1e-6:
        return None, "not charge balanced in the ABX2/A2BCX4 scheme"
    tbl = _bin_table(cls)
    terms, missing, tot = [], [], 0.0
    for c, ncat in sorted(cats.items()):
        v = val(c)
        for X, nx in sorted(ans.items()):
            fX = nx / nX
            bcomp = {1: {c: 2, X: 1}, 2: {c: 1, X: 1}, 3: {c: 2, X: 3}, 4: {c: 1, X: 2}}[v]
            coeff = (ncat / 2.0 if v in (1, 3) else ncat) * fX
            hit = tbl.get(_reduced(bcomp))
            if hit is None:
                missing.append("".join(f"{e}{int(n) if n != 1 else ''}" for e, n in sorted(bcomp.items())))
                continue
            nm, dh, cf, var, th, efu = hit
            terms.append({"coeff": round(coeff, 4), "phase": nm, "E_pfu": round(dh, 4),
                          "E_fu_tot": round(efu, 4),
                          "contribution": round(coeff * dh, 4), "run": var})
            tot += coeff * dh
    if missing:
        return None, ("no archived same-footing run for the canonical binar" +
                      ("y " if len(set(missing)) == 1 else "ies ") + ", ".join(sorted(set(missing))))
    S_terms = _mix_entropy(name)
    S = round(sum(x["contribution_eV"] for x in S_terms), 6)
    d0 = round(dHf_fu - tot, 4)
    return {"kind": "stoichiometric binary decomposition (canonical A2X/BX/B2X3/CX2 set over the anion mix)",
            "E_pfu": round(dHf_fu, 4), "pre": 1, "sum": round(tot, 4), "S": S, "S_used": S,
            "S_terms": S_terms, "d0": d0, "d": round(d0 + S, 4), "terms": terms}, None

_BD_CACHE = {}
def binary_decomp(cls, name, comp_fu, dHf_fu):
    """comp_fu: per-f.u. composition of the host; dHf_fu: its same-class formation enthalpy per f.u."""
    host_key = _reduced(comp_fu)
    ck = (cls, host_key)
    if ck in _BD_CACHE:
        cached = _BD_CACHE[ck]
        if cached is None: return None
        bestv, bestmix = cached
    else:
        els = sorted(set(e for e, n in comp_fu.items() if n > 0))
        cands = [c for c in _binaries(cls, set(els)) if _reduced(c[2]) != host_key]   # never itself
        if not cands:
            _BD_CACHE[ck] = None; return None
        A = _np.array([[c2[2].get(e, 0.0) for c2 in cands] for e in els])
        b = _np.array([comp_fu.get(e, 0.0) for e in els])
        cvec = _np.array([c2[1] for c2 in cands])
        x = _simplex_lp(cvec, A, b)
        if x is None:
            _BD_CACHE[ck] = None; return None
        bestv = float(cvec @ x)
        bestmix = [(cands[i][0], float(x[i]), cands[i][1], cands[i][3], (cands[i][5] if len(cands[i])>5 else None)) for i in range(len(cands)) if x[i] > 1e-9]
        _BD_CACHE[ck] = (bestv, bestmix)
    S_terms = _mix_entropy(name)
    S = round(sum(t["contribution_eV"] for t in S_terms), 6)
    d0 = round(dHf_fu - bestv, 4)
    return {"kind": "stoichiometric binary decomposition", "E_pfu": round(dHf_fu, 4),
            "pre": 1, "sum": round(bestv, 4), "S": S, "S_used": S, "S_terms": S_terms,
            "d0": d0, "d": round(d0 + S, 4),
            "terms": [{"coeff": round(c2, 4), "phase": nm, "E_pfu": round(dh, 4),
                       "E_fu_tot": (round(efu, 4) if efu is not None else None),
                       "contribution": round(c2 * dh, 4), "run": var} for nm, c2, dh, var, efu in bestmix]}


# ---- the released ChalcoDB dataset (paper d6el00026f): per-run band gap and SLME as published.
# Our EIGENVAL band-counting collapsed 3,299 HSE+SOC gaps to ~0-0.3 eV on runs whose lattices are
# byte-identical to the release (wide-gap I-III-VI2 sulfides at 0.04 eV are unphysical), and our
# 500 nm SLME used a different thickness convention than the paper's (ref 35). Where the release
# row matches this run (same name+ordering, same lattice), its gap and SLME are the published
# values and are used, with provenance shown on the panel.
try:
    CHALCODB = json.load(open(f"{LOG}/chalcodb_release.json"))
except Exception:
    CHALCODB = {}
n_rel = {"gap": 0, "slme_val": []}

byname = collections.defaultdict(dict)         # (theory, name) -> {ord: row}
n_foot = {}
dos_keys, run_keys = [], []
n_dos = n_runs = 0
t0 = time.time()

for (theory, name, poly), members in sorted(groups.items()):
    members.sort(key=lambda t: (t[1]["F_per_atom"], t[0]))
    # ground state = lowest energy among the members whose run is verifiably of this theory's
    # footing; a lower-energy member from a mislabelled/other-footing run must not win
    _okm = [m for m in members if classify_row(m[1]["theory"], m[1])["mode"] == "ok"]
    key, r, _ = (_okm or members)[0]
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
    # ---- energetics, re-derived within one footing class (see "run footing" above) ----------
    dterms = None
    ef_pa = None
    no_decomp_reason = None
    fc = classify_row(r["theory"], r)
    Fe, nate = fc["F"], fc["nat"]
    comp_atoms = None
    if comp and nate:
        toks = _tokens(r["compound"])
        tsum = sum(n for _, n in toks)
        if toks and tsum > 0 and abs(nate / tsum - round(nate / tsum)) < 1e-6:
            scale = nate / tsum
            comp_atoms = {}
            for e, n in toks: comp_atoms[e] = comp_atoms.get(e, 0.0) + n * scale
        elif fc["mode"] == "ok":
            comp_atoms = dict(comp)
    en_note = fc["note"]
    refs_used = {}
    if fc["cls"] and Fe is not None and nate and comp_atoms and fc["mode"] != "diverged":
        ef_pa, refs_used, missing = formation_pa(fc["cls"], Fe, nate, comp_atoms, fc["pots"])
        if missing:
            en_note = ((en_note + "; ") if en_note else "") + \
                f"no {class_label(fc['cls'])} elemental reference for {', '.join(missing)}: formation energy withheld"
        elif Fe / nate > 0 or abs(ef_pa) > 3.5:
            en_note = ((en_note + "; ") if en_note else "") + \
                f"the run energy is not physical ({Fe/nate:+.2f} eV/atom, formation energy {ef_pa:+.2f} eV/atom): diverged or broken run, everything withheld"
            ef_pa = None; fc["keep_props"] = False
    if ef_pa is not None:
        # formula unit = the name's stoichiometry, gcd-reduced when integral (Cd108Se27Te81 -> Cd4SeTe3);
        # fractional (alloy) names keep their own unit so the mixing-entropy term is per the same f.u.
        _tk = _tokens(r["compound"])
        _g = 1
        if _tk and all(abs(n - round(n)) < 1e-6 for _, n in _tk):
            _g = 0
            for _, n in _tk: _g = math.gcd(_g, int(round(n)))
            _g = _g or 1
        comp_fu = {}
        for e, n in _tk: comp_fu[e] = comp_fu.get(e, 0.0) + n / _g
        n_fu_atoms = sum(comp_fu.values()) or 1
        n_distinct = len([e for e, n in comp_fu.items() if n > 0])
        if n_distinct <= 2:
            dterms = None      # element or binary: dHf IS the stability measure; no decomposition defined
        else:
            dterms, why = chalcodb_decomp(fc["cls"], r["compound"], comp_fu, ef_pa * n_fu_atoms)
            if dterms is None and ("valence" in (why or "") or "charge balanced" in (why or "") or "partition" in (why or "")):
                dterms = binary_decomp(fc["cls"], r["compound"], comp_fu, ef_pa * n_fu_atoms)
                if dterms is not None:
                    dterms["kind"] = "stoichiometric decomposition (outside the ABX2/A2BCX4 valence scheme: linear programme over all same-footing binaries and elements)"
            if dterms is None:
                no_decomp_reason = why or "no same-footing binary set could be assembled"
    edec_fu = dterms["d"] if dterms else None
    foot_info = {"class": fc["cls"], "label": class_label(fc["cls"]) if fc["cls"] else None,
                 "encut": fc["enc"], "mode": fc["mode"], "refs": refs_used}
    if dterms is not None:
        dterms["footing"] = foot_info
    elif en_note or fc["mode"] != "ok":
        dterms = {"withheld": en_note or "energetics not derivable", "footing": foot_info}
    elif ef_pa is not None:
        dterms = {"footing": foot_info}       # an element/binary or a host with nothing to decompose into
        if no_decomp_reason: dterms["no_decomp"] = no_decomp_reason
    if en_note and "terms" in (dterms or {}):
        dterms["note"] = en_note
    if not fc["keep_props"]:
        eps3, eps_avg, slme = None, None, None
        dr = None                            # a DOS from a run of another footing is not this row's
    n_foot[fc["mode"]] = n_foot.get(fc["mode"], 0) + 1


    row = [
        (round(ef_pa, 6) if ef_pa is not None else None),      # 0 formation energy, eV/atom (same-footing)
        edec_fu,                                                # 1 decomposition energy, eV/f.u.
        r.get("gap") if fc["keep_props"] else None,             # 2 band gap
        r.get("eps_avg"),                                       # 3 dielectric constant
        None,                                                   # 4 SLME -- see note below
        Fe,                                                     # 5 total energy of the run the energetics use
        nate,                                                   # 6 atoms in that cell
        (foot_info["label"] or ""),                             # 7 footing class -> REFS key
        [round(r[k], 4) for k in ("a", "b", "c")] if (r.get("a") and fc["keep_props"]) else None,   # 8 lattice
        (dterms.get("S") if dterms else None),                  # 9 ideal-mixing entropy, eV/f.u.
        fmax,                                                   # 10 final max force
        r.get("vbm") if fc["keep_props"] else None,             # 11
        r.get("cbm") if fc["keep_props"] else None,             # 12
        eps3,                                                   # 13 dielectric tensor
        None,                                                   # 14 SLME(thickness)
        r.get("direct") if fc["keep_props"] else None,          # 15 direct gap?
        r.get("eps_source"),                                    # 16 where eps came from
        r.get("kmesh"),                                         # 17
        [round(r[k], 2) for k in ("alpha", "beta", "gamma")] if (r.get("alpha") and fc["keep_props"]) else None,  # 18
        ([t["phase"] for t in dterms["terms"]] if (dterms and dterms.get("terms")) else None),   # 19 phases it decomposes to
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
    # gap: where our EIGENVAL counting collapsed the gap on a release-identical run, the released
    # gap repairs it (labelled). SLME is NEVER copied: it is always recomputed here from this
    # run's own absorption spectrum (user directive 2026-08-18) -- the release enters SLME only
    # through the labelled gap onset on repaired rows, and as a printed validation below.
    if theory == "HSE+SOC" and poly in ("kesterite", "stannite") and fc["keep_props"]:
        rel = CHALCODB.get(f"{name}_{poly}")
        if rel and row[8] and rel.get("abc") and max(abs(a - b) for a, b in zip(row[8], rel["abc"])) < 0.02:
            if rel.get("g") is not None and (row[2] is None or abs(row[2] - rel["g"]) > 0.05):
                row[2] = rel["g"]
                row[11] = row[12] = None             # our VBM/CBM counting produced the wrong gap here
                if isinstance(row[27], dict):
                    row[27] = dict(row[27]); row[27]["gap_source"] = "released dataset (d6el00026f)"
                n_rel["gap"] += 1
                # gap changed -> recompute SLME from our spectrum with the repaired onset
                if r.get("abs_E") and r.get("abs_alpha"):
                    try: row[4] = slme_500nm(list(zip(r["abs_E"], r["abs_alpha"])), row[2])
                    except Exception: row[4] = None
                    row[14] = [[0.5, row[4]]] if row[4] is not None else None
                if isinstance(row[27], dict) and row[4] is not None:
                    row[27]["slme_source"] = ("recomputed here (Yu-Zunger, 500 nm, fr = 1) from this "
                                              "run's absorption spectrum, with the released gap as onset")
            if rel.get("slme") is not None and row[4] is not None:
                n_rel["slme_val"].append(row[4] - rel["slme"])
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
    if r.get("abs_E") and r.get("abs_alpha") and fc["keep_props"]:
        # alpha(E) as [E, alpha] pairs, which is the shape the detail panel already reads
        optics[sk] = {"abs": [[e, a] for e, a in zip(r["abs_E"], r["abs_alpha"])],
                      "slme": ([[0.5, slme]] if slme is not None else None),
                      "eps": eps3, "source": r.get("alpha_source")}

print(f"tars written in {time.time() - t0:.0f}s")
_sv = sorted(abs(x) for x in n_rel["slme_val"])
print(f"release ingest: gaps repaired {n_rel['gap']}; SLME recomputed everywhere (never copied)")
if _sv:
    print(f"SLME validation vs released dataset ({len(_sv)} matched rows): "
          f"median |d| {_sv[len(_sv)//2]:.2f}  p90 {_sv[int(len(_sv)*.9)]:.2f}  max {_sv[-1]:.2f} pct-points "
          f"(thickness/fr conventions differ; comparison only)")
print("row footing modes:", n_foot)

# ---- cross-check gate: a formation energy is a property of the structure, and between PBEsol and
# a hybrid built on it (or PBE) it moves by tens of meV/atom (this library: median 0.064, p99 0.42
# eV/atom over 12,640 pairs). An ordering whose same-footing E_f sits > 0.5 eV/atom from the PBEsol
# value of the SAME compound and ordering, or > 0.3 eV/atom (total energy) above the other
# ordering of the same compound at the same theory, is an unconverged/broken run (K2Ba1Ge1S2Te2
# HSE kesterite: -3.07 vs -4.71 eV/atom for its stannite, PBEsol -4.04 for both) -- withheld, with
# both numbers quoted, rather than published as a +13 eV/f.u. decomposition energy.
def _withhold(v, why):
    foot = (v[27] or {}).get("footing") if len(v) > 27 and isinstance(v[27], dict) else None
    v[27] = {"withheld": why, "footing": foot}
    for i in (0, 1, 2, 3, 4, 8, 9, 11, 12, 13, 14, 15, 18, 19):
        v[i] = None
n_x = {"vs_pbesol": 0, "vs_ordering": 0}
for (theory, name), ords in byname.items():          # pass 1: against PBEsol, same structure
    if theory == "PBEsol": continue
    for o, v in ords.items():
        if v[0] is None: continue
        pv = byname.get(("PBEsol", name), {}).get(o)
        if pv is not None and pv[0] is not None and abs(v[0] - pv[0]) > 0.5:
            _withhold(v, (f"the same-footing formation energy here ({v[0]:+.3f} eV/atom) differs from the PBEsol "
                          f"value for the same compound and ordering ({pv[0]:+.3f} eV/atom) by "
                          f"{abs(v[0]-pv[0]):.2f} eV/atom; across this library that difference is 0.06 eV/atom "
                          f"(median) and 0.42 (99th percentile), so this run is not converged -- withheld"))
            n_x["vs_pbesol"] += 1
for (theory, name), ords in byname.items():          # pass 2: against the other, still-valid orderings
    for o, v in ords.items():
        if v[0] is None: continue
        if len(ords) > 1 and v[5] is not None and v[6]:
            others = [w[5] / w[6] for oo, w in ords.items() if oo != o and w[0] is not None and w[5] is not None and w[6]]
            if others and (v[5] / v[6]) - min(others) > 0.3:
                _withhold(v, (f"this ordering's total energy ({v[5]/v[6]:.3f} eV/atom) sits "
                              f"{(v[5]/v[6]) - min(others):.2f} eV/atom above the other ordering of the same compound "
                              f"at this theory ({min(others):.3f} eV/atom); cation orderings differ by tens of meV/atom "
                              f"in every converged case, so this run is not converged -- withheld"))
                n_x["vs_ordering"] += 1
print("cross-check gate withheld:", n_x)
# their optics/DOS entries go with them
_gone = set()
for (theory, name), ords in byname.items():
    for o, v in ords.items():
        if len(v) > 27 and isinstance(v[27], dict) and v[27].get("withheld") and v[2] is None:
            _gone.add(struct_key(name, theory, o))
optics = {k: x for k, x in optics.items() if k not in _gone}
dos_keys = [k for k in dos_keys if k not in _gone]

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

# ---- duplicate host twins ("Al_i in AgAlSe2 ordering 1 shows only Neutral"): the archive holds
# a suffix-less copy of many kesterite/stannite hosts carrying ONLY the neutral per-site scan of
# the same defects (gs like Al_i-5), while the _kesterite/_stannite row of the same host carries
# the full charge ladder. Publishing both made the bare row look like a defect with no charged
# data. Drop the bare row when a suffixed twin with the same (theory, defect) exists and the bare
# row has no charge state the twin lacks.
_twin = {(r["theory"], r["host"], r["defect"]) for r in dd}
def _qs(r):
    out = set()
    for v in (r.get("vertices") or {}).values():
        for c in (v.get("charges") or {}).values(): out.add(c.get("q"))
    return out
_qmap = {}
for r in dd: _qmap[(r["theory"], r["host"], r["defect"])] = _qs(r)
_dropped = 0
_keep = []
for r in dd:
    h = r["host"]
    if not re.search(r"_(kesterite|stannite)$", h):
        twins = [(r["theory"], h + s, r["defect"]) for s in ("_kesterite", "_stannite")]
        tw = [k for k in twins if k in _twin]
        if tw and _qmap[(r["theory"], h, r["defect"])] <= set().union(*(_qmap[k] for k in tw)):
            _dropped += 1
            continue
    _keep.append(r)
print(f"bare-host twin rows dropped: {_dropped} (their charge states are a subset of the suffixed ordering row)")
dd = _keep

defects = []
for r in dd:
    theory = THEORY.get(r["theory"], r["theory"])
    fk = FK.get(theory, theory)
    vx = {}
    e = {}
    corr = {}
    dos_by_q = {}
    # Per-charge-state settings gate. build_all gates on the NEUTRAL dE/atom only; ZnTe HSE+SOC
    # Vac_Te had a sane neutral run and charged runs 160 eV off it (different reference /
    # settings), which published Ef@VBM = 159.5 eV. A charge state whose dE differs from the
    # neutral by more than 15 eV cannot be the same calculation; withhold it with a reason.
    dE_neu = None
    for v0 in (r.get("vertices") or {}).values():
        for c0 in (v0.get("charges") or {}).values():
            if c0.get("q") == 0 and c0.get("dE") is not None:
                dE_neu = c0["dE"]
    # ---- whole-ladder physics gates (2026-08-18, "some defect formation energy is crazy negative").
    # Every term of Ef must come from one consistent chain; three broken patterns were live:
    #   1. neutral dE far off any physical scale (Al_i in K0.5Ag0.5Al1S1Te1: +129 eV for every
    #      charge -- consistent with each other, so the per-charge gate passed, all garbage);
    #   2. the host reference scaled from a small k-converged cell while the supercell ran
    #      Gamma-only (ZnTe HSE+SOC: hpa from the 6-atom cell; the 215-atom Vac_Zn cell is MORE
    #      bound per atom than the perfect crystal -- impossible -- and 14 meV/atom of k-mesh
    #      error becomes 3.1 eV in dE, publishing Ef(V_Zn) = -2.3 eV);
    #   3. mixed-footing mu0 (no true HSE+SOC Zn elemental run exists; chempot fell back to the
    #      HSE06-base value).
    # A defect whose NEUTRAL formation energy comes out below -0.2 eV at any solved vertex claims
    # the host decays spontaneously -- for hosts the bulk side shows stable, that is a broken
    # chain, not physics. Withhold Ef for the WHOLE ladder (the charged states share the same
    # host reference and mu set), keep dE/DOS/structures, and say exactly why.
    ladder_note = None
    nat_r = r.get("natoms")
    if dE_neu is not None and nat_r and abs(dE_neu) / nat_r > 0.05:
        ladder_note = (f"the neutral run is {dE_neu:+.1f} eV off the host reference "
                       f"({dE_neu/nat_r:+.3f} eV/atom): not the same calculation settings")
    if ladder_note is None and dE_neu is not None and r.get("host_F_per_atom") is not None        and nat_r and r.get("n_pristine"):
        dn_r = r.get("dn") or {}
        if dn_r and all(n <= 0 for n in dn_r.values()):        # pure removal (vacancies)
            epa_def = (r["host_F_per_atom"] * r["n_pristine"] + dE_neu) / nat_r
            if epa_def < r["host_F_per_atom"] - 0.003:
                ladder_note = (f"the defect cell is more bound per atom ({epa_def:.4f} eV) than the "
                               f"perfect crystal ({r['host_F_per_atom']:.4f} eV), which is impossible for a "
                               f"vacancy at one set of settings: the host reference (scaled from a "
                               f"{r.get('host_natoms')}-atom cell) is not consistent with this supercell")
    if ladder_note is None and dE_neu is not None:
        neg = None
        for v0 in (r.get("vertices") or {}).values():
            c0 = next((c for c in (v0.get("charges") or {}).values() if c.get("q") == 0), None)
            if c0 and c0.get("Ef_VBM") is not None and c0["Ef_VBM"] < -0.2:
                neg = c0["Ef_VBM"]
        if neg is not None:
            ladder_note = (f"the neutral formation energy comes out {neg:+.2f} eV, i.e. the host would "
                           f"form this defect spontaneously -- the bulk data shows this host stable, so "
                           f"the chain (host reference / chemical potentials) is not consistent")
    for vname, v in (r.get("vertices") or {}).items():
        ch = {}
        for cname, c in (v.get("charges") or {}).items():
            q = str(c["q"])
            # Band-edge transition-level gate ("Vac_Ba in Cu1.5Ag0.5BaSnS4 is negative"): each added
            # electron must cost at least ~E_VBM, so the average (0/q) level implied by the run,
            # s = -(dE_q - dE_0)/q - E_VBM, must sit near or inside the gap. Vac_Ba's q=-2 run gives
            # s = -1.39 eV (its (-1/-2) level 2.77 eV BELOW the VBM -- impossible), which published
            # Ef@VBM = -1.24/-1.69 while passing the crude 15 eV gate. Allow -0.7 eV of band-edge/
            # negative-U slack for acceptors, -1.5 for donors (shallow-donor levels sit below VBM
            # legitimately); anything deeper is a charge-state run inconsistent with its own neutral.
            if dE_neu is not None and c.get("dE") is not None and c.get("q") not in (0, None) \
               and r.get("host_vbm") is not None and c.get("Ef_VBM") is not None:
                _s = -(c["dE"] - dE_neu) / c["q"] - r["host_vbm"]
                if (c["q"] < 0 and _s < -0.7) or (c["q"] > 0 and _s < -1.5):
                    c = dict(c)
                    c["Ef_VBM"] = None; c["Ef_CBM"] = None
                    c["note"] = (f"the average (0/{q}) transition level implied by this run sits "
                                 f"{-_s:.2f} eV below the VBM, which is impossible -- this charge state's "
                                 f"run is not consistent with its own neutral; withheld")
            if dE_neu is not None and c.get("dE") is not None and c.get("q") != 0 \
               and abs(c["dE"] - dE_neu) > 15.0 and c.get("Ef_VBM") is not None:
                c = dict(c)
                c["Ef_VBM"] = None; c["Ef_CBM"] = None
                c["note"] = (f"charge state {q} is {c['dE']-dE_neu:+.1f} eV off the neutral run "
                             "-- not the same calculation settings; withheld")
            if ladder_note and c.get("Ef_VBM") is not None:
                c = dict(c)
                c["Ef_VBM"] = None; c["Ef_CBM"] = None
                c["note"] = "formation energies withheld: " + ladder_note
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
# one reference set per footing class (keyed by the label the row carries in v[7]); the mu shown
# per element is the plain-PAW one where several PAWs exist, and the row's own breakdown lists the
# exact PAW/mu pair it used
for _cls, _tab in EREF.items():
    _el = {}
    for _sym, _ref in sorted(_tab.items(), key=lambda kv: (kv[1]["el"], kv[0] != kv[1]["el"], kv[0])):
        _el.setdefault(_ref["el"], round(_ref["mu"], 6))
    refs[class_label(_cls)] = {"el": _el, "bin": {}, "paw_mu": {s: round(x["mu"], 6) for s, x in _tab.items()},
                               "class": _cls}

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
