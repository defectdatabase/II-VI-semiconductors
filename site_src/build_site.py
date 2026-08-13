#!/usr/bin/env python3
"""Inject defect entries (PBEsol 7 hosts + HSE+SOC CdTe) and the 6763-compound
bulk table into the site template. Per-charge energies and mus are nullable."""
import csv, json, pathlib

repo = pathlib.Path.home() / "Desktop/Habibur_Rahman/II-VI-semiconductors"
scratch = pathlib.Path(__file__).parent

def f(x):
    try:
        return float(x)
    except (ValueError, TypeError):
        return None

def load_defects(path, func):
    out, dropped = [], 0
    for r in csv.DictReader(open(path)):
        pure = f(r["Toten_pure"])
        if pure is None or f(r["VBM"]) is None or f(r["gap"]) is None:
            dropped += 1
            continue
        e = {}
        for c, q in [("p2", "2"), ("p1", "1"), ("neut", "0"), ("m1", "-1"), ("m2", "-2")]:
            t, k = f(r["Toten_" + c]), f(r["Corr_" + c])
            if t is not None and k is not None:
                e[q] = round(t + k - pure, 4)
        if not e:
            dropped += 1
            continue
        out.append({"f": func, "h": r["AB"].strip(), "d": r["Defect"], "t": r["Type"],
                    "g": f(r["gap"]), "v": f(r["VBM"]), "e": e,
                    "mc": f(r["mu_Cd_rich"]), "mt": f(r["mu_Te_rich"])})
    return out, dropped

defects, drop1 = load_defects(repo / "cdsete_defect_library_generation_pbesol.csv", "pbesol")
hse, drop2 = load_defects(repo / "cdte_hse_soc.csv", "hsesoc")
defects += hse

compounds = []
for r in csv.DictReader(open(repo / "chalcodb_slim.csv")):
    name = r["compound"]
    struct = ""
    if "_" in name:
        name, struct = name.rsplit("_", 1)
    name = name.replace("1", "") if name.count("1") and False else name
    compounds.append([name, struct, f(r["eform"]), f(r["edecomp"]), f(r["gap"]),
                      f(r["eps"]), f(r["slme"])])

tpl = (scratch / "template.html").read_text()
html = tpl.replace("/*__DATA__*/", json.dumps(defects, separators=(",", ":")))
html = html.replace("/*__COMPOUNDS__*/", json.dumps(compounds, separators=(",", ":")))
(repo / "docs/index.html").write_text(html)
print(f"defects: {len(defects)} (pbesol {len(defects)-len(hse)}, hsesoc {len(hse)}; dropped {drop1}+{drop2})")
print(f"compounds: {len(compounds)}")
