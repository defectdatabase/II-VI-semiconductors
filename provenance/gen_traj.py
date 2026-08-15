"""Relaxation trajectories for the bulk rows, from each run's own XDATCAR.

The payload shipped `trajKeys: []`, so the "Relaxation movie" button never appeared on any row
even though most runs have many ionic steps -- the step table was the only place they showed.

Frame format is the one the viewer already reads:
  {"bulk": {"species":[...], "nframes":N, "frames":[{"i":step,"e":energy,"f":maxforce,
                                                     "lat":[[3x3]],"p":[[x,y,z],...]}]}}
Key is the template's own: HSE06 rows use host__hse2x2x1__<name>_<polymorph>, everything else
host__<fk>__<name>.
"""
import os, re, io, sys, gzip, json, glob, tarfile, collections

B = "/eagle/wbg_defects/chalcogenide_defects"; L = f"{B}/log"
SHARD = int(sys.argv[1]) if len(sys.argv) > 1 else 0
NSHARD = int(sys.argv[2]) if len(sys.argv) > 2 else 1
THEORY = {"PBE":"PBE","PBEsol":"PBEsol","HSE":"HSE06","HSE+SOC":"HSE+SOC","PBE+U":"PBE+U"}
FK = {"PBE":"pbe","PBEsol":"pbesol","HSE06":"hse","HSE+SOC":"hse_soc","PBE+U":"pbe_u"}
POLY = re.compile(r"^(?P<base>.+?)_(?P<poly>kesterite|stannite|zincblende|wurtzite|rocksalt|"
                  r"chalcopyrite|reference|supercell)(?:-(?P<cfg>\d+))?$")


def split_name(c):
    m = POLY.match(c)
    if m: return m.group("base"), m.group("poly")
    m2 = re.match(r"^(?P<b>.+?)-(?P<c>\d+)$", c)
    return (m2.group("b"), "reference") if m2 else (c, "reference")


def movie_key(name, theory, poly):
    if theory == "HSE06":
        return f"host__hse2x2x1__{name}_{poly}"
    return f"host__{FK.get(theory, 'pbe')}__{name}"


def op(p):
    if os.path.exists(p): return open(p, errors="ignore")
    if os.path.exists(p + ".gz"): return gzip.open(p + ".gz", "rt", errors="ignore")
    return None


def has(p): return os.path.exists(p) or os.path.exists(p + ".gz")


def xdatcar(d):
    """all ionic configurations; the lattice is re-read per frame when the cell moves (vc-relax)"""
    fh = op(f"{d}/XDATCAR")
    if not fh:
        return None
    try:
        lines = fh.read().splitlines()
    finally:
        fh.close()
    if len(lines) < 8:
        return None
    try:
        scale = float(lines[1].split()[0])
        lat = [[float(x) * scale for x in lines[i].split()[:3]] for i in (2, 3, 4)]
        els = lines[5].split()
        cnt = [int(x) for x in lines[6].split()]
    except (ValueError, IndexError):
        return None
    if not els or not re.fullmatch(r"[A-Z][a-z]?", els[0]):
        return None
    nat = sum(cnt)
    species = []
    for e, n in zip(els, cnt):
        species += [e] * n
    frames, i = [], 0
    n = len(lines)
    cur_lat = lat
    while i < n:
        line = lines[i]
        if line.strip().startswith("Direct configuration") or line.strip().lower().startswith("direct"):
            pts = []
            for j in range(i + 1, min(i + 1 + nat, n)):
                v = lines[j].split()
                if len(v) < 3:
                    break
                try:
                    pts.append([round(float(v[0]), 5), round(float(v[1]), 5), round(float(v[2]), 5)])
                except ValueError:
                    break
            if len(pts) == nat:
                # Unwrap against the previous frame. XDATCAR writes fractional coordinates folded
                # into [0,1), so an atom sitting at z = 0.0001 reappears at 0.9999 and the viewer
                # shows it teleporting across the cell instead of relaxing -- max |delta| came out
                # as exactly 1.0 while the real displacement was 5e-5.
                if frames:
                    prev = frames[-1]["p"]
                    for ai in range(nat):
                        for k in range(3):
                            dlt = pts[ai][k] - prev[ai][k]
                            if dlt > 0.5:
                                pts[ai][k] = round(pts[ai][k] - 1.0, 5)
                            elif dlt < -0.5:
                                pts[ai][k] = round(pts[ai][k] + 1.0, 5)
                frames.append({"lat": [[round(x, 5) for x in r] for r in cur_lat], "p": pts})
            i += nat
        elif i > 6 and len(line.split()) == 1 and frames:
            # a vc-relax writes a fresh header between configurations
            try:
                s2 = float(lines[i + 1].split()[0])
                cur_lat = [[float(x) * s2 for x in lines[i + 1 + k].split()[:3]] for k in (1, 2, 3)]
                i += 7
                continue
            except (ValueError, IndexError):
                pass
        i += 1
    if not frames:
        return None
    return {"species": species, "frames": frames}


steps = {}
for f in glob.glob(f"{L}/steps2_bulk_*.jsonl"):
    for line in open(f):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("path"):
            steps[r["path"]] = r.get("steps") or []

bulk = json.load(open(f"{L}/derived_bulk.json"))
groups = collections.defaultdict(list)
for k, r in bulk.items():
    base, poly = split_name(r["compound"])
    groups[(THEORY.get(r["theory"], r["theory"]), base, poly)].append(r)


def run_dir(r):
    c = f"{B}/DFT/bulk/{r['theory']}/{r['compound']}"
    if has(f"{c}/XDATCAR"): return c
    if os.path.isdir(c):
        for s in sorted(os.listdir(c)):
            p = f"{c}/{s}"
            if os.path.isdir(p) and has(f"{p}/XDATCAR"): return p
    return None


items = sorted(groups.items())
tf = tarfile.open(f"{L}/payload/trajs_{SHARD}.tar", "w")
keys, st = [], collections.Counter()
for gi, ((theory, name, poly), members) in enumerate(items):
    if gi % NSHARD != SHARD:
        continue
    members.sort(key=lambda x: x["F_per_atom"])
    r = members[0]
    d = run_dir(r)
    if not d:
        st["no_xdatcar"] += 1
        continue
    tr = xdatcar(d)
    if not tr or len(tr["frames"]) < 2:
        st["single_frame" if tr else "unparsed"] += 1
        continue
    sl = steps.get(d.replace(B + "/", "")) or []
    for i, fr in enumerate(tr["frames"]):
        fr["i"] = i + 1
        if i < len(sl):
            fr["e"] = sl[i].get("E")
            fr["f"] = sl[i].get("fmax")
    key = movie_key(name, theory, poly)
    blob = {"bulk": {"species": tr["species"], "nframes": len(tr["frames"]),
                     "frames": tr["frames"]}}
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
        g.write(json.dumps(blob, separators=(",", ":")).encode())
    data = buf.getvalue()
    ti = tarfile.TarInfo(f"trajs/{key}.json.gz"); ti.size = len(data); ti.mtime = 0
    tf.addfile(ti, io.BytesIO(data))
    keys.append(key)
    st["traj"] += 1
    st[f"frames_{min(len(tr['frames']),10)}"] += 1
tf.close()
json.dump(sorted(set(keys)), open(f"{L}/payload/trajkeys_{SHARD}.json", "w"))
print(f"shard {SHARD}: {dict(st)}", flush=True)
