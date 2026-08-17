"""Precompute defect-site annotation for EVERY defect row, data-side, with numpy.
Output log/dmarks.json: key -> {mk:[site indices], vc:[{el,abc}], m:method, why:reason-if-none}.
Mirrors the frontend algorithm (score-picked host incl. reference/ordering variants +
primitive replication) so the client only has to READ the answer."""
import json, os, re, gzip, io, tarfile, collections
import numpy as np

B = "/eagle/wbg_defects/materialsHUB/telluride"
L = f"{B}/log"
rows = json.load(open(f"{L}/derived_defect.json"))
TH_FK = {"HSE": "hse", "HSE+SOC": "hse_soc", "PBE": "pbe", "PBE+U": "pbe_u", "PBEsol": "pbesol"}
PFX = {"pbesol": "PBEsol__", "hse": "HSE06__", "hse_soc": "", "pbe": "pbe__", "pbe_u": "pbe__"}

# ---- structures: extract once to a temp dir (fast random access) ----
SDIR = f"{L}/structures_tmp"
if not os.path.isdir(SDIR):
    os.makedirs(SDIR)
    import glob as g
    for t in g.glob(f"{L}/payload/structures*.tar"):
        with tarfile.open(t) as tf:
            for m in tf.getmembers():
                if m.isfile():
                    out = f"{SDIR}/{os.path.basename(m.name)}"
                    if not os.path.exists(out):
                        open(out, "wb").write(tf.extractfile(m).read())
HAVE = set(os.listdir(SDIR))

def load_struct(key):
    p = f"{key}.json"
    if p not in HAVE: return None
    d = json.load(open(f"{SDIR}/{p}"))
    lat = np.array(d["lattice"]["matrix"], float)
    abc = np.array([s["abc"] for s in d["sites"]], float)
    els = [s["species"][0]["element"] for s in d["sites"]]
    return {"lat": lat, "abc": abc, "els": els}

# ---- defect final frames from the dtrajs tars (archived names) ----
def traj_index():
    import glob as g
    idx = {}
    for t in sorted(g.glob(f"{L}/payload/dtrajs_*.tar")) + sorted(g.glob(f"{L}/payload/trajs_fix*.tar")):
        with tarfile.open(t) as tf:
            for m in tf.getmembers():
                if m.isfile() and not os.path.basename(m.name).startswith("host__"):
                    idx[os.path.basename(m.name)[:-8]] = (t, m.name)
    return idx
TIDX = traj_index()

def load_final_frame(fk, host, dirname):
    ent = TIDX.get(f"{fk}__{host}__{dirname}")
    if not ent: return None
    with tarfile.open(ent[0]) as tf:
        d = json.load(gzip.open(io.BytesIO(tf.extractfile(ent[1]).read())))
    t = d.get("0") or d[sorted(d)[0]]
    fr = t["frames"][-1]
    return {"lat": np.array(fr.get("lat") or t.get("lat"), float),
            "abc": np.array(fr["p"], float), "els": t["species"]}

def min_image_d(lat, dfrac):
    dfrac = dfrac - np.round(dfrac)
    cart = dfrac @ lat
    return np.linalg.norm(cart, axis=-1)

def mismatch(st, host):
    # per defect site: distance+element of nearest host site
    d = st["abc"][:, None, :] - host["abc"][None, :, :]
    d -= np.round(d)
    cart = np.einsum("ijk,kl->ijl", d, st["lat"])
    dist = np.linalg.norm(cart, axis=2)
    j = dist.argmin(axis=1)
    bd = dist[np.arange(len(j)), j]
    bel = np.array(host["els"], object)[j]
    return bd, bel, dist

def replicate(prim, lat, wantN):
    M = lat @ np.linalg.inv(prim["lat"])
    Mr = np.round(M)
    if np.abs(M - Mr).max() > 0.05: return None
    det = int(round(np.linalg.det(Mr)))
    if det <= 0 or abs(det * len(prim["els"]) - wantN) > 9: return None
    Mi = np.linalg.inv(Mr)
    lim = int(np.abs(Mr).max()) + 1
    pts, els = [], []
    rng = range(-lim, lim + 1)
    for s_abc, el in zip(prim["abc"], prim["els"]):
        for i in rng:
            for jj in rng:
                for k in rng:
                    f = (s_abc + [i, jj, k]) @ Mi
                    if np.all(f > -1e-6) and np.all(f < 1 - 1e-6):
                        pts.append(np.clip(f, 0, 1)); els.append(el)
    if len(pts) != det * len(prim["els"]): return None
    return {"lat": lat, "abc": np.array(pts), "els": els}

def host_candidates(fk, host):
    p = PFX.get(fk, "pbe__")
    c = []
    if fk == "hse_soc": c.append(host)
    if fk == "pbesol": c.append("PBEsol__" + host)
    if fk == "hse": c.append("HSE06__" + host)
    c.append((fk if fk in PFX else "pbe") + "__" + host)
    for x in (p + host + "_reference", "HSE06__" + host + "_reference",
              "PBEsol__" + host + "_reference", host + "_reference", "pbe__" + host + "_reference"):
        if x not in c: c.append(x)
    if not re.search(r"_(kesterite|stannite)$", host):
        for o in ("kesterite", "stannite"):
            c.append(p + host + "_" + o)
    return c

def label_parts(d):
    out = []
    for part in re.sub(r"-\d+$", "", d).split("+"):
        m = re.fullmatch(r"([A-Z][a-z]?|Vac)_([A-Z][a-z]?|i)", part)
        if not m: return None
        out.append(m.groups())
    return out

res = {}
stats = collections.Counter()
for key, r in rows.items():
    th, fk = r["theory"], TH_FK[r["theory"]]
    host, defect = r["host"], r["defect"]
    dirname = r.get("archived_as") or defect
    st = load_final_frame(fk, host, dirname); src_fk = fk
    if st is None:
        st = load_final_frame("pbesol", host, dirname); src_fk = "pbesol"
    if st is None:
        res[key] = {"why": "no relaxed geometry archived"}
        stats["no geometry"] += 1
        continue
    # pick best size-compatible host by mismatch score; replicate primitive as fallback
    best, bestScore, smallest = None, 10**9, None
    for hk in host_candidates(fk, host):
        h = load_struct(hk)
        if h is None: continue
        if smallest is None or len(h["els"]) < len(smallest["els"]): smallest = h
        if abs(len(h["els"]) - len(st["els"])) > 8: continue
        bd, bel, _ = mismatch(st, h)
        sc = int(np.sum((bd > 1.2) | (bel != np.array(st["els"], object))))
        if sc < bestScore: best, bestScore = h, sc
        if bestScore <= 2: break
    if best is None and smallest is not None and len(smallest["els"]) < len(st["els"]):
        rep = replicate(smallest, st["lat"], len(st["els"]))
        if rep is not None:
            bd, bel, _ = mismatch(st, rep)
            if int(np.sum((bd > 1.2) | (bel != np.array(st["els"], object)))) <= 8:
                best = rep
    dn = r.get("dn") or {}
    want_atoms = sum(int(v) for v in dn.values() if v > 0)
    want_vac = -sum(int(v) for v in dn.values() if v < 0)
    # a substitution A_B is +1 A / -1 B in dn but ONE site on screen: the vacated B site is
    # where the marked A now sits. Vacancy rings are only for the NET missing atoms.
    n_sub = min(want_atoms, want_vac)
    want_vac_ring = want_vac - n_sub
    if best is None:
        # composition-only fallback: mark foreign elements
        hostels = set(re.findall(r"[A-Z][a-z]?", host))
        mk = [i for i, e in enumerate(st["els"]) if e not in hostels][:max(want_atoms, 1)]
        if mk:
            res[key] = {"mk": mk, "tk": f"{src_fk}__{host}__{dirname}", "m": "foreign-element (no commensurate host cell)"}
            stats["foreign-element"] += 1
        else:
            res[key] = {"why": "no commensurate host cell and no foreign element to mark"}
            stats["unmarkable"] += 1
        continue
    bd, bel, dist = mismatch(st, best)
    score = (bel != np.array(st["els"], object)) * 10 + bd + (bd > 1.2) * 5
    order = np.argsort(-score)
    keep = want_atoms if want_atoms else min(int(np.sum((bd > 1.2) | (bel != np.array(st["els"], object)))), 6)
    mk = sorted(int(i) for i in order[:keep]) if keep else []
    # vacancies: host sites with no defect atom within 1.2 A
    hb = dist.min(axis=0)
    vidx = [int(i) for i in np.where(hb > 1.2)[0]]
    vidx.sort(key=lambda i: -hb[i])
    # drop host sites that a marked atom now occupies -- a relaxed substituent can sit up to
    # ~2 A off the ideal site, so use half a bond length (2.2 A), not 1.2 A
    cand_v = []
    for i in vidx:
        v = {"el": best["els"][i], "abc": [round(float(x), 5) for x in best["abc"][i]]}
        if mk:
            dv = min_image_d(st["lat"], st["abc"][mk] - np.array(v["abc"]))
            if dv.min() < 2.2: continue
        cand_v.append(v)
    vc = cand_v[:want_vac_ring] if dn else cand_v[:min(len(cand_v), 6)]
    if dn and len(mk) > want_atoms: mk = mk[:want_atoms]
    res[key] = {"mk": mk, "vc": vc, "tk": f"{src_fk}__{host}__{dirname}", "m": "host-diff" + (" (replicated primitive)" if best is not None and smallest is not None and best is not smallest and len(best["els"]) != len(smallest["els"]) and False else "")}
    stats["marked" if (mk or vc) else "clean-cell (nothing to mark)"] += 1
json.dump(res, open(f"{L}/dmarks.json", "w"))
print(dict(stats), "total", len(res))
