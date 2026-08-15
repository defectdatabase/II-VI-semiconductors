"""Dissolve surfaces_catalysis: nothing stays outside bulk/ and defect/ (user directive).

  slab + adsorbed H + a point defect  -> defect, host named with the adsorbate so it can never be
                                         composition-matched against the clean monolayer
  pristine slab optimisation / bands / optics / AIMD -> bulk, one variant per sub-run
  input-only directories with no VASP output          -> quarantine, since there is no result
"""
import os, re, sys, gzip, collections
B = "/eagle/wbg_defects/chalcogenide_defects"
S = f"{B}/surfaces_catalysis"
APPLY = "--apply" in sys.argv
st = collections.Counter()
def op(p):
    if os.path.exists(p): return open(p, errors="ignore")
    if os.path.exists(p+".gz"): return gzip.open(p+".gz","rt",errors="ignore")
def has_run(d): return op(f"{d}/OSZICAR") is not None
def theory_of(d):
    fh = op(f"{d}/INCAR")
    if not fh: return None
    t = fh.read().upper(); fh.close()
    def on(k): return k in t and ".TRUE." in t.split(k,1)[1][:24]
    th = "HSE" if on("LHFCALC") else ("PBEsol" if re.search(r"GGA\s*=\s*PS", t) else "PBE")
    if on("LSORBIT"): th += "+SOC"
    if on("LDAU"): th += "+U"
    return th
def mv(s, t):
    print("  ", s.replace(B+"/",""), "->", t.replace(B+"/",""))
    if not APPLY: return
    os.makedirs(os.path.dirname(t), exist_ok=True)
    if os.path.exists(t): st["collision"] += 1; return
    os.rename(s, t); st["moved"] += 1

# 1) photocatalysis: slab + H + defect  -> defect
pc = f"{S}/ZnIn2X4_GGA_U_Photo_Catalysis/H"
if os.path.isdir(pc):
    for defect in sorted(os.listdir(pc)):
        dd = f"{pc}/{defect}"
        if not os.path.isdir(dd): continue
        for c in sorted(os.listdir(dd)):
            cd = f"{dd}/{c}"
            if os.path.isdir(cd) and has_run(cd):
                mv(cd, f"{B}/DFT/defect/{theory_of(cd) or 'PBE+U'}/ZnIn2S4_monolayer_H/{defect}/{c}")
                st["defect"] += 1
            elif has_run(dd):
                break
        if has_run(dd):
            mv(dd, f"{B}/DFT/defect/{theory_of(dd) or 'PBE+U'}/ZnIn2S4_monolayer_H/{defect}/Neutral")
            st["defect"] += 1

# 2) Project_1: a mix of pristine slab work AND charged point defects. A path component of the
# form `q=<n>` under `defects/` marks a CHARGE STATE, so those go to defect/, not bulk -- the
# first pass sent `defects/q=+2/In_Zn` to bulk, which is a defect wearing a bulk label.
QRE = re.compile(r"^q=(?P<q>[+-]?\d+)$")
for root, dirs, files in os.walk(f"{S}/ZnIn2X4_Project_1"):
    if not has_run(root): continue
    rel = root.replace(f"{S}/ZnIn2X4_Project_1/", "")
    parts = rel.split("/")
    comp = re.sub(r"^Ultrathin_", "", parts[0]) if parts else "ZnIn2X4"
    th = theory_of(root) or "PBE"
    qidx = next((i for i, p in enumerate(parts) if QRE.match(p)), None)
    if qidx is not None and qidx + 1 < len(parts):
        q = int(QRE.match(parts[qidx]).group("q"))
        cdir = "Neutral" if q == 0 else f"Charged{q:+d}"
        defect = parts[qidx + 1]
        mv(root, f"{B}/DFT/defect/{th}/{comp}_monolayer/{defect}/{cdir}")
        st["defect_from_project1"] += 1
    else:
        variant = "_".join(parts[1:]) or "run"
        mv(root, f"{B}/DFT/bulk/{th}/{comp}_monolayer/{variant}")
        st["bulk"] += 1
    dirs[:] = []

# 3) anything left with no VASP output at all
for name in sorted(os.listdir(S)) if os.path.isdir(S) else []:
    d = f"{S}/{name}"
    if not os.path.isdir(d): continue
    runs = sum(1 for r, _dd, ff in os.walk(d) if "OSZICAR" in ff or "OSZICAR.gz" in ff)
    if runs == 0:
        mv(d, f"{B}/quarantine_non_physics/no_vasp_output__{name}")
        st["no_output"] += 1
    else:
        print("   LEFT", name, runs, "runs")
print(dict(st))
if not APPLY: print("dry run")

