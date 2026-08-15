"""Normalise host and compound names, and remove campaign-purpose naming from the tree.

Three defects being fixed, all mine:

  fake hosts     the ZnIn2S4 defect hosts were derived from each DEFECT cell's host-element
                 composition, so a Zn vacancy produced host `Zn17In36S72` and an In antisite
                 `Zn17In37S72`. The host is a property of the PRISTINE, not of the defect: every
                 one of them is ZnIn2S4.
  _monolayer     dropped -- the compound is the compound (user directive). The slab nature is
                 already recorded by the cell in each run.
  purpose names  `GGA_U_optimization_bulk` is not a compound, and a variant called
                 `defect_calculations_hse` inside bulk/ reads like a defect folder. Renamed to
                 neutral variant labels; nothing is merged away.
"""
import os, re, sys, collections
B = "/eagle/wbg_defects/chalcogenide_defects"
APPLY = "--apply" in sys.argv
ZN = re.compile(r"^Zn\d*In\d*S\d*(_monolayer)?$")
st = collections.Counter(); plan = []

VARIANT = {"defect_calculations_hse": "pristine_hse_campaign",
           "defect_calculations_gga_u": "pristine_ggau_campaign",
           "defects_bulk": "pristine_defect_campaign",
           "loptics": "optics"}

def mv(s, t):
    plan.append((s, t))
    if not APPLY: return
    os.makedirs(os.path.dirname(t), exist_ok=True)
    if os.path.exists(t):
        # never overwrite: fold as an extra variant instead
        base = t; i = 2
        while os.path.exists(f"{base}-{i}"): i += 1
        t = f"{base}-{i}"
        st["folded_as_variant"] += 1
    os.rename(s, t); st["moved"] += 1

def clean_compound(name):
    # an adsorbate is part of the system, not decoration: keep the _H, drop only "_monolayer"
    if name.endswith("_monolayer_H"):
        return "ZnIn2S4_H"
    n = name[:-len("_monolayer")] if name.endswith("_monolayer") else name
    if ZN.match(name) or ZN.match(n):
        return "ZnIn2S4"
    if n in ("GGA_U_optimization_bulk", "HSE_optimization_bulk", "Ultrathin_ZnIn2S4"):
        return "ZnIn2S4"
    return n

# --- defect hosts
for th in sorted(os.listdir(f"{B}/DFT/defect")):
    tp = f"{B}/DFT/defect/{th}"
    if not os.path.isdir(tp): continue
    for host in sorted(os.listdir(tp)):
        new = clean_compound(host)
        if new == host: continue
        src, dst = f"{tp}/{host}", f"{tp}/{new}"
        if os.path.isdir(dst):
            # merge defect-by-defect so nothing is clobbered
            for defect in sorted(os.listdir(src)):
                sd, td = f"{src}/{defect}", f"{dst}/{defect}"
                if os.path.isdir(td):
                    for c in sorted(os.listdir(sd)):
                        mv(f"{sd}/{c}", f"{td}/{c}"); st["merged_charge"] += 1
                else:
                    mv(sd, td); st["merged_defect"] += 1
        else:
            mv(src, dst); st["renamed_host"] += 1

# --- bulk compounds and their variants
for th in sorted(os.listdir(f"{B}/DFT/bulk")):
    tp = f"{B}/DFT/bulk/{th}"
    if not os.path.isdir(tp): continue
    for comp in sorted(os.listdir(tp)):
        cp = f"{tp}/{comp}"
        if not os.path.isdir(cp): continue
        for v in sorted(os.listdir(cp)):
            if os.path.isdir(f"{cp}/{v}") and v in VARIANT:
                mv(f"{cp}/{v}", f"{cp}/{VARIANT[v]}"); st["renamed_variant"] += 1
        new = clean_compound(comp)
        if new != comp:
            src, dst = f"{tp}/{comp}", f"{tp}/{new}"
            if os.path.isdir(dst):
                for v in sorted(os.listdir(src)):
                    mv(f"{src}/{v}", f"{dst}/{v}"); st["merged_variant"] += 1
            else:
                mv(src, dst); st["renamed_compound"] += 1

print("planned", len(plan), dict(st))
for s, t in plan[:10]: print("   ", s.replace(B+"/",""), "->", t.replace(B+"/",""))
if not APPLY: print("dry run")
