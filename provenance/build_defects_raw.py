"""Assemble the defect table from raw ingredients:
E(q): raw OSZICAR F  ·  E_pristine: raw host Bulk F  ·  VBM/gap: raw EIGENVAL band counting
mu: archived chem_pot engine outputs (defect_mu_table)  ·  Corr: original eFNV campaign (labeled)
CdTe HSE+SOC stays CSV-sourced (raw runs not retained) and is labeled as such."""
import csv, json, pathlib, re
from collections import defaultdict

SP = pathlib.Path("/private/tmp/claude-501/-Users-mdhabiburrahman/82412357-0812-4060-8f7f-4a2204f5844f/scratchpad")
repo = pathlib.Path.home() / "Desktop/Habibur_Rahman/chalcogenide-defects"

def f(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return None

# ---------- raw F values ----------
F = defaultdict(dict)          # (th,host,defect) -> {cdir: (F, conv, nelect)}
FB = {}                        # (th,host) -> bulk F
for r in csv.DictReader(open(SP / "recompute/defects_F.csv")):
    th, host, d, cd = r["theory"], r["host"], r["defect"], r["cdir"]
    if host == "chem_pot" or not r["F"]:
        continue
    if d == "BULK":
        FB[(th, host)] = float(r["F"])
        continue
    F[(th, host, d)][cd] = (float(r["F"]), r["conv"] == "1", f(r["nelect"]))

# ---------- lib bulk fallback (INCAR vintage may differ from defect runs; disclosed) ----------
LIBF = {}
# ---------- raw band edges ----------
edges = {}
libmap = {"lib_pbesol": "pbesol", "lib_hse_soc": "hsesoc"}
for r in csv.DictReader(open(SP / "recompute/host_edges.csv")):
    if r["src"] == "libBulk" and r["F"]:
        thl = libmap.get(r["theory"])
        if thl:
            LIBF[(thl, r["host"])] = float(r["F"])
    if not r["vbm"]:
        continue
    th = r["theory"] if r["src"] == "hostBulk" else libmap.get(r["theory"])
    if th is None:
        continue
    key = (th, r["host"])
    if r["src"] == "hostBulk" or key not in edges:
        edges[key] = (float(r["vbm"]), float(r["gap"]))

# ---------- mu tables ----------
def host_from_dir(name):
    if name.startswith("Cd108"):
        m = re.match(r"Cd108Se(\d+)Te(\d+)", name)
        if m:
            x = int(m.group(1)) / (int(m.group(1)) + int(m.group(2)))
            cands = [("CdSe0.06Te0.94", .06), ("CdSe0.12Te0.88", .12), ("CdSe0.20Te0.80", .20),
                     ("CdSe0.25Te0.75", .25), ("CdSe0.50Te0.50", .50), ("CdSe0.75Te0.25", .75)]
            return min(cands, key=lambda c: abs(x - c[1]))[0]
    return name

MU = defaultdict(dict)         # (th,host) -> {defect: (mu_cat_rich, mu_an_rich)}
cur = None
for line in open(SP / "recompute/mu_dump.txt"):
    line = line.strip()
    if line.startswith("###FILE"):
        _, th, path = line.split(None, 2)
        hostdir = path.split("/chem_pot_results/")[1].split("/")[0]
        cur = (th, host_from_dir(hostdir))
        header = True
        continue
    if cur is None or not line:
        continue
    parts = line.split(",")
    if parts[0] == "Defect":
        continue
    if len(parts) >= 3:
        a, b = f(parts[1]), f(parts[2])
        if a is not None and b is not None:
            MU[cur][parts[0]] = (a, b)
    elif len(parts) == 2:                      # single-facet alloy tables (anion-rich)
        b = f(parts[1])
        if b is not None:
            MU[cur][parts[0]] = (None, b)

def mu_of(th, host, defect):
    tab = MU.get((th, host), {})
    mc, mt = 0.0, 0.0
    mc_ok = True
    for part in defect.split("+"):
        v = tab.get(part)
        if v is None:
            return None, None
        if v[0] is None:
            mc_ok = False
        else:
            mc += v[0]
        mt += v[1]
    return (round(mc, 4) if mc_ok else None), round(mt, 4)

# ---------- corrections from the original campaign CSVs ----------
CORR = {}
def load_corr(path, th):
    for r in csv.DictReader(open(path)):
        host = r["AB"].strip()
        for c, q in [("p2", "2"), ("p1", "1"), ("neut", "0"), ("m1", "-1"), ("m2", "-2")]:
            k = f(r["Corr_" + c])
            if k is not None:
                CORR[(th, host, r["Defect"], q)] = k
load_corr(repo / "cdsete_defect_library_generation_pbesol.csv", "pbesol")
load_corr(repo / "cdte_hse_soc.csv", "hsesoc")

CH = {"Neutral": "0", "Charged+1": "1", "Charged+2": "2", "Charged-1": "-1", "Charged-2": "-2"}
out = []
stats = defaultdict(int)
for (th, host, d), runs in sorted(F.items()):
    fb = FB.get((th, host)); bulk_src = "host Bulk"
    if fb is None:
        fb = LIBF.get((th, host)); bulk_src = "library bulk"
    ed = edges.get((th, host))
    if fb is None or ed is None:
        stats["no_bulk_or_edges"] += 1
        continue
    # q from NELECT where possible
    n0 = runs.get("Neutral", (None, None, None))[2]
    e, u = {}, {}
    for cd, (Fv, conv, ne) in runs.items():
        q = CH.get(cd)
        if q is None or not conv:
            stats["dropped_unconv" if q else "odd_dir"] += 1
            continue
        if n0 is not None and ne is not None:
            qn = int(round(n0 - ne))
            if str(qn) != q:
                stats["nelect_mismatch"] += 1
                q = str(qn)          # NELECT is ground truth
        de = round(Fv - fb, 4)
        k = CORR.get((th, host, d, q))
        if q == "0":
            e[q] = round(de + (k or 0.0), 4)
        elif k is not None:
            e[q] = round(de + k, 4)
        else:
            u[q] = de                # charged, no correction available -> disclosed separately
    if not e:
        stats["no_neutral"] += 1
        continue
    mc, mt = mu_of(th, host, d)
    rec = {"f": th, "h": host, "d": d, "t": "raw", "g": round(ed[1], 4), "v": round(ed[0], 4),
           "e": e, "mc": mc, "mt": mt, "src": "raw" + ("" if bulk_src == "host Bulk" else " (library bulk ref)")}
    if u:
        rec["u"] = u
    out.append(rec)
    stats["published"] += 1

# CdTe HSE+SOC: raw runs not retained -> keep compiled-table rows, labeled
kept = 0
for r in csv.DictReader(open(repo / "cdte_hse_soc.csv")):
    pure = f(r["Toten_pure"])
    if pure in (None, 0.0):
        continue
    e = {}
    for c, q in [("p2", "2"), ("p1", "1"), ("neut", "0"), ("m1", "-1"), ("m2", "-2")]:
        tv, k = f(r["Toten_" + c]), f(r["Corr_" + c])
        if tv not in (None, 0.0) and k is not None:
            e[q] = round(tv + k - pure, 4)
    if not e:
        continue
    out.append({"f": "hsesoc", "h": "CdTe", "d": r["Defect"], "t": "csv",
                "g": f(r["gap"]), "v": f(r["VBM"]), "e": e,
                "mc": f(r["mu_Cd_rich"]), "mt": f(r["mu_Te_rich"]), "src": "campaign table"})
    kept += 1

print(dict(stats), "| CdTe hsesoc rows kept:", kept, "| total:", len(out))
mu_missing = sum(1 for r in out if r["mc"] is None and r["mt"] is None)
print("rows without any mu:", mu_missing)
from collections import Counter
missparts = Counter()
for r in out:
    if r["mc"] is None and r["mt"] is None and r["f"] == "pbesol":
        tab = MU.get((r["f"], r["h"]), {})
        for part in r["d"].split("+"):
            if part not in tab:
                missparts[part] += 1
print("missing mu parts (pbesol):", dict(missparts.most_common(12)))
json.dump(out, open(SP / "recompute/defects_payload_raw.json", "w"), separators=(",", ":"))

# anchor: V_Cd CdTe pbesol
for r in out:
    if r["h"] == "CdTe" and r["d"] == "V_Cd" and r["f"] == "pbesol":
        best = {}
        for cond, mu in [("Cd-rich", r["mc"]), ("Te-rich", r["mt"])]:
            if mu is None:
                continue
            vals = [r["e"][q] + mu + int(q) * r["v"] for q in r["e"]]
            best[cond] = round(min(vals), 3)
        print("ANCHOR raw V_Cd CdTe pbesol Ef@VBM:", best, "| VBM", r["v"], "gap", r["g"], "| e:", r["e"])
