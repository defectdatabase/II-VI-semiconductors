"""Restore the polymorph from the PRE-RENAME extraction snapshot, not by guessing.

The cell-shape test failed: kesterite and stannite are both tetragonal with near-identical axis
ratios, so it was picking noise (five distinct variants all landed on kesterite). The correct
source is `phys_defect_*.jsonl`, written BEFORE the rename -- 4,419 of its records still carry
`<host>_<polymorph>` together with the run's final energy. Match on (energy, atom count) and the
original name comes back exactly. This is the same recovery that undid the interstitial-tag
collapse earlier in this project, and it only works because extraction ran before renaming.
"""
import os, re, sys, gzip, json, glob, collections
B = "/eagle/wbg_defects/chalcogenide_defects"
APPLY = "--apply" in sys.argv
st = collections.Counter(); plan = []

def op(p):
    if os.path.exists(p): return open(p, errors="ignore")
    if os.path.exists(p+".gz"): return gzip.open(p+".gz","rt",errors="ignore")
def lastF(d):
    fh=op(f"{d}/OSZICAR")
    if not fh:
        fh=op(f"{d}/OUTCAR")
        if not fh: return None
        E=None
        for line in fh:
            if "energy(sigma->0)" in line:
                try: E=float(line.split()[-1])
                except Exception: pass
        fh.close(); return E
    F=None
    for line in fh:
        if " F= " in line:
            t=line.split()
            try: F=float(t[t.index("F=")+1])
            except Exception: pass
    fh.close(); return F

# (theory, rounded F) -> (host_with_polymorph, defect, charge)
idx = {}
for f in glob.glob(f"{B}/log/phys_defect_*.jsonl"):
    for line in open(f):
        try: r=json.loads(line)
        except Exception: continue
        h=r.get("host") or ""
        if ("kesterite" not in h and "stannite" not in h) or r.get("F") is None: continue
        idx.setdefault((r.get("theory"), round(r["F"], 4)), (h, r.get("defect"), r.get("charge")))
print("pre-rename index entries:", len(idx))

for th in sorted(os.listdir(f"{B}/DFT/defect")):
    droot=f"{B}/DFT/defect/{th}"
    if not os.path.isdir(droot): continue
    for host in sorted(os.listdir(droot)):
        hp=f"{droot}/{host}"
        if not os.path.isdir(hp) or re.search(r"_(kesterite|stannite)$", host): continue
        for defect in sorted(os.listdir(hp)):
            dp=f"{hp}/{defect}"
            if not os.path.isdir(dp): continue
            for ch in sorted(os.listdir(dp)):
                src=f"{dp}/{ch}"
                if not os.path.isdir(src): continue
                F=lastF(src)
                if F is None: st["no_energy"] += 1; continue
                hit=idx.get((th, round(F, 4)))
                if not hit: st["not_in_snapshot"] += 1; continue
                oh, od, _oc = hit
                if not oh.startswith(host): st["host_mismatch"] += 1; continue
                tgt=f"{droot}/{oh}/{od or defect}/{ch}"
                if src == tgt: continue
                plan.append((src, tgt)); st["restore"] += 1
                if APPLY:
                    os.makedirs(os.path.dirname(tgt), exist_ok=True)
                    if os.path.exists(tgt): st["collision"] += 1
                    else: os.rename(src, tgt); st["moved"] += 1
print("planned", len(plan), dict(st))
for s_,t_ in plan[:6]: print("   ", s_.replace(B+"/",""), "->", t_.replace(B+"/",""))
if not APPLY: print("dry run")
