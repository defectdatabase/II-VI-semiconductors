"""Element-projected DOS from vasprun.xml <partial>, for the runs whose DOSCAR is gone.

I claimed the projections "were never written". That was wrong, and the audit says so: of 250
sampled runs that came out total-only, ALL 250 set LORBIT=11, the DOSCAR is simply ABSENT for 227
of them, and vasprun.xml is present for 250/250. VASP writes the same per-ion projection into
vasprun.xml's <partial> block, so it is recoverable for every one of them.

Streaming parse: the <dos> section sits near the end of the file, so this reads line by line and
keeps only the partial block -- a 500 MB vasprun is never held in memory.
"""
import os, re, io, sys, gzip, json, glob, tarfile, collections

B = "/eagle/wbg_defects/chalcogenide_defects"; L = f"{B}/log"
SHARD = int(sys.argv[1]) if len(sys.argv) > 1 else 0
NSHARD = int(sys.argv[2]) if len(sys.argv) > 2 else 1
NUM = re.compile(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?")


def op(p):
    if os.path.exists(p):
        return open(p, errors="ignore")
    if os.path.exists(p + ".gz"):
        return gzip.open(p + ".gz", "rt", errors="ignore")
    return None


def species_of(d):
    fh = op(f"{d}/CONTCAR") or op(f"{d}/POSCAR")
    if not fh:
        return None
    try:
        ls = [fh.readline() for _ in range(7)]
    finally:
        fh.close()
    try:
        els, cnt = ls[5].split(), [int(x) for x in ls[6].split()]
    except (ValueError, IndexError):
        return None
    if not els or not re.fullmatch(r"[A-Z][a-z]?", els[0]):
        return None
    out = []
    for e, n in zip(els, cnt):
        out += [e] * n
    return out


def partial_dos(d):
    fh = op(f"{d}/vasprun.xml")
    if not fh:
        return None
    sp = species_of(d)
    if not sp:
        fh.close()
        return None
    ef = None
    in_dos = in_partial = False
    ion = -1
    per_ion = []
    cur = None
    energies = None
    try:
        for line in fh:
            if ef is None and "efermi" in line:
                m = NUM.search(line.split(">", 1)[-1])
                if m:
                    try: ef = float(m.group(0))
                    except ValueError: pass
            if "<dos" in line:
                in_dos = True
            elif in_dos and "<partial" in line:
                in_partial = True
            elif in_partial and "</partial>" in line:
                break
            elif in_partial:
                if 'comment="ion' in line:
                    ion += 1
                    cur = []
                    per_ion.append(cur)
                elif line.lstrip().startswith("<r>") and cur is not None:
                    v = NUM.findall(line)
                    if len(v) >= 2:
                        try:
                            cur.append((float(v[0]), sum(float(x) for x in v[1:])))
                        except ValueError:
                            pass
    finally:
        fh.close()
    if not per_ion or len(per_ion) < len(sp):
        return None
    n = min(len(p) for p in per_ion[:len(sp)] if p) if any(per_ion[:len(sp)]) else 0
    if n == 0:
        return None
    energies = [per_ion[0][i][0] for i in range(n)]
    el = collections.defaultdict(lambda: [0.0] * n)
    for ia in range(len(sp)):
        rows = per_ion[ia]
        if len(rows) < n:
            continue
        acc = el[sp[ia]]
        for i in range(n):
            acc[i] += rows[i][1]
    if ef is None:
        ef = 0.0
    step = max(1, n // 600)
    return {"ef": round(ef, 4),
            "e": [round(energies[i] - ef, 4) for i in range(0, n, step)],
            "total": [round(sum(el[k][i] for k in el), 4) for i in range(0, n, step)],
            "el": {k: [round(v[i], 4) for i in range(0, n, step)] for k, v in el.items()},
            "projected": True, "source": "vasprun.xml <partial>"}


targets = []
for f in glob.glob(f"{L}/dos_*.jsonl"):
    for line in open(f):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("path") and not r.get("projected"):
            targets.append((r["path"], r.get("compound"), r.get("theory"), r.get("variant")))
targets = sorted(set(targets))
mine = [t for i, t in enumerate(targets) if i % NSHARD == SHARD]
print(f"shard {SHARD}/{NSHARD}: {len(mine)} of {len(targets)} not-projected runs", flush=True)

out = f"{L}/vpdos_{SHARD}.jsonl"
n = ok = 0
with open(out, "w") as fh:
    for rel, comp, th, var in mine:
        n += 1
        d = partial_dos(f"{B}/{rel}")
        if d:
            d.update({"path": rel, "compound": comp, "theory": th, "variant": var})
            fh.write(json.dumps(d) + "\n")
            ok += 1
        if n % 100 == 0:
            fh.flush()
            print(f"  {n} scanned, {ok} recovered", flush=True)
print(f"shard {SHARD} done: {n} scanned, {ok} element-projected recovered", flush=True)
