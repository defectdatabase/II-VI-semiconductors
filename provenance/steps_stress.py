"""Per-ionic-step energy, force AND stress, plus the run's own INCAR / POTCAR / KPOINTS.

Stress comes from the OUTCAR `in kB` line that VASP prints once per ionic step:
    in kB    -12.34567   -12.34567   -11.98765    0.00001   0.00002   0.00003
(xx yy zz xy yz zx, in kBar). The reported number is max|component|, and the full six are kept.

One pass over each OUTCAR yields all of it -- reading the file more than once is what made the
first extraction slow on multi-GB outputs.
"""
import os, re, sys, gzip, json, glob

B = "/eagle/wbg_defects/chalcogenide_defects"
LOG = f"{B}/log"
SHARD = int(sys.argv[1]) if len(sys.argv) > 1 else 0
NSHARD = int(sys.argv[2]) if len(sys.argv) > 2 else 1
KIND = sys.argv[3] if len(sys.argv) > 3 else "bulk"
NUM = re.compile(r"^-?\d+\.?\d*(?:[eE][-+]?\d+)?$")


def op(p):
    if os.path.exists(p):
        return open(p, errors="ignore")
    if os.path.exists(p + ".gz"):
        return gzip.open(p + ".gz", "rt", errors="ignore")
    return None


def parse(d):
    fh = op(f"{d}/OUTCAR")
    if not fh:
        return None
    incar, potcar, steps = {}, [], []
    kmesh = ediffg = None
    cur_forces = None
    fmax = fatom = None
    pending_stress = None
    in_incar = False
    prevE = None
    try:
        for line in fh:
            if "TITEL" in line and "=" in line:
                potcar.append(line.split("=", 1)[1].strip())
            elif line.startswith(" generate k-points for:"):
                kmesh = "x".join(line.split(":")[1].split())
            elif "EDIFFG" in line:
                m = re.search(r"EDIFFG\s*=\s*([-\d.E+]+)", line)
                if m:
                    try: ediffg = float(m.group(1))
                    except ValueError: pass
            elif "in kB" in line:
                v = [x for x in line.replace("in kB", "").split() if NUM.match(x)]
                if len(v) >= 6:
                    f = [float(x) for x in v[:6]]
                    pending_stress = {"max": round(max(abs(x) for x in f), 4),
                                      "xx": f[0], "yy": f[1], "zz": f[2],
                                      "xy": f[3], "yz": f[4], "zx": f[5]}
            elif "TOTAL-FORCE" in line:
                cur_forces = 0                      # count of force rows read, not a flag:
                fmax = fatom = None                 # VASP prints a dashed rule immediately after
                nat_seen = 0                        # the header, and treating that as the
            elif cur_forces is not None:            # terminator ended the block before it began
                v = line.split()
                if len(v) == 6 and NUM.match(v[0]) and NUM.match(v[3]):
                    try:
                        fx, fy, fz = float(v[3]), float(v[4]), float(v[5])
                    except ValueError:
                        continue
                    f = (fx * fx + fy * fy + fz * fz) ** 0.5
                    if fmax is None or f > fmax:
                        fmax, fatom = f, nat_seen
                    nat_seen += 1
                    cur_forces += 1
                elif cur_forces > 0:
                    cur_forces = None
            elif "free  energy   TOTEN" in line:
                m = re.search(r"=\s*(-?\d+\.\d+)", line)
                if m:
                    E = float(m.group(1))
                    st = {"n": len(steps) + 1, "E": round(E, 6),
                          "dE": None if prevE is None else round(E - prevE, 6),
                          "fmax": None if fmax is None else round(fmax, 5),
                          "fmax_atom": fatom}
                    if pending_stress:
                        st["stress"] = pending_stress["max"]
                        st["stress_tensor"] = [round(pending_stress[k], 3)
                                               for k in ("xx", "yy", "zz", "xy", "yz", "zx")]
                    steps.append(st)
                    prevE = E
                    pending_stress = None
                    fmax = fatom = None
    finally:
        fh.close()
    fh = op(f"{d}/INCAR")
    if fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                incar[k.strip().upper()] = v.split("#")[0].split("!")[0].strip()
        fh.close()
    fh = op(f"{d}/KPOINTS")
    if fh and not kmesh:
        ls = fh.read().splitlines(); fh.close()
        if len(ls) >= 4:
            v = ls[3].split()
            if len(v) >= 3 and all(x.isdigit() for x in v[:3]):
                kmesh = "x".join(v[:3])
    return {"incar": incar, "potcar": potcar, "kmesh": kmesh, "ediffg": ediffg,
            "n_steps": len(steps), "steps": steps,
            "F": steps[-1]["E"] if steps else None,
            "force_converged": (steps and steps[-1].get("fmax") is not None
                                and ediffg is not None and steps[-1]["fmax"] < abs(ediffg))}


pat = "DFT/bulk/*/*" if KIND == "bulk" else "DFT/defect/*/*/*/*"
dirs = set()
for p in (pat, pat + "/*"):
    for name in ("OUTCAR", "OUTCAR.gz"):
        for f in glob.glob(f"{B}/{p}/{name}"):
            dirs.add(os.path.dirname(f))
dirs = sorted(dirs)
mine = [d for i, d in enumerate(dirs) if i % NSHARD == SHARD]
print(f"shard {SHARD}/{NSHARD} {KIND}: {len(mine)} of {len(dirs)}", flush=True)
out = f"{LOG}/steps2_{KIND}_{SHARD}.jsonl"
n = 0
with open(out, "w") as fh:
    for d in mine:
        r = parse(d)
        if not r:
            continue
        rel = d.replace(B + "/", "")
        parts = rel.split("/")
        r["path"] = rel
        r["kind"] = parts[1]
        r["theory"] = parts[2] if len(parts) > 2 else None
        if parts[1] == "bulk":
            r["compound"] = parts[3] if len(parts) > 3 else None
            r["variant"] = parts[4] if len(parts) > 4 else None
        else:
            r["host"] = parts[3] if len(parts) > 3 else None
            r["defect"] = parts[4] if len(parts) > 4 else None
            r["charge"] = parts[5] if len(parts) > 5 else None
        fh.write(json.dumps(r) + "\n")
        n += 1
        if n % 500 == 0:
            fh.flush(); print(f"  {n}", flush=True)
print(f"shard {SHARD} done: {n}", flush=True)
