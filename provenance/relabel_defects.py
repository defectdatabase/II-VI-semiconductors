#!/usr/bin/env python3
"""Relabel the defect rows of docs/data.json so every label encodes its own cell.

The 2026-08-17 dn audit (Eagle log/audit_dn_mismatch.json, copied here) compared every
commensurate defect row's directory label against the integer atom-exchange dn of its
relaxed cell: 669 of 4,371 labels contradict the cell. The energies were always priced
from the cell, so the numbers stand; only the labels move.

Convention (the same one audit_dn.py checks): Vac_X -> {X:-1}; A_B -> {A:+1, B:-1};
A_i -> {A:+1}; complexes are "+"-joined parts; multiplicities repeat the part. When dn
admits more than one label (two added species contest one removed site), the relaxed
geometry decides: log/contested_geometry.json records which added atom sits on the
vacancy site. Rows whose cell is pristine (dn = {}) are not defects and are withheld.
Rows whose pristine reference is not on disk (four PBE CdTe rows) and the two contested
HSE complex_ rows keep their old labels and are listed as held in the report.

Collisions: when two rows in the same (theory, host) land on the same label they are
distinct relaxed configurations of that defect, and the tree's own rule applies --
more than one configuration is numbered -1..-N (provenance/README.md, 2026-08-15).

Applies to: defects[].d, defects[].dos values, trajKeys, dosKeys, and the backing
files in docs/trajs/ and docs/dos/. Writes provenance/defect_relabels.json as the
durable record. Idempotent: re-running after application reports nothing to do.
"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROV = REPO / "provenance"
DATA = REPO / "docs" / "data.json"

FK = {"PBE": "pbe", "PBEsol": "pbesol", "HSE": "hse", "HSE+SOC": "hse_soc", "PBE+U": "pbe_u"}
ANIONS = {"O", "S", "Se", "Te", "N", "P", "As", "Sb", "F", "Cl", "Br", "I", "C"}

# Held out of the automatic pass: dn alone cannot decide these, and either the pristine
# reference is not on disk (PBE CdTe 218-atom cells) or the tree config family behind the
# payload row must be picked first (the two HSE complex_ rows). Six rows keep old labels.
HELD = {
    "pbe|CdTe|As_i+Cl_i", "pbe|CdTe|As_i+O_i", "pbe|CdTe|As_i+P_i", "pbe|CdTe|As_i+Sb_i",
    "hse|CdTe|complex_As+1+Cd+1+Cl+1", "hse|CdTe|complex_As+1+Cd+1+O+1",
}


def role(el: str) -> str:
    return "A" if el in ANIONS else "C"


def all_labels(dn):
    add = sorted(e for e, v in dn.items() if v > 0 for _ in range(round(v)))
    rem = sorted(e for e, v in dn.items() if v < 0 for _ in range(round(-v)))
    out = set()

    def rank(p):
        return (0 if p.startswith("Vac_") else (2 if p.endswith("_i") else 1), p)

    def rec(a, r, parts):
        if not a or not r:
            p = list(parts) + [f"Vac_{b}" for b in r] + [f"{x}_i" for x in a]
            out.add("+".join(sorted(p, key=rank)))
            return
        for x in set(a):
            for b in set(r):
                a2 = list(a); a2.remove(x)
                r2 = list(r); r2.remove(b)
                rec(a2, r2, parts + [f"{x}_{b}"])

    rec(add, rem, [])
    return sorted(out)


def label_dn(label):
    out = {}
    for part in label.split("+"):
        a, _, site = part.partition("_")
        if a == "Vac":
            out[site] = out.get(site, 0) - 1
        elif site == "i":
            out[a] = out.get(a, 0) + 1
        else:
            out[a] = out.get(a, 0) + 1
            out[site] = out.get(site, 0) - 1
    return {e: v for e, v in out.items() if v}


def preferred_label(dn, old):
    labels = all_labels(dn)
    if len(labels) == 1:
        return labels[0], False
    old_subs = [p for p in (s.split("-")[0] for s in old.split("+"))
                if "_" in p and not p.startswith("Vac") and p.split("_")[1] != "i"]
    if old_subs:
        hit = [l for l in labels
               if all(s in l.split("+") for s in old_subs)]
        if len(hit) == 1:
            return hit[0], False

    def score(l):
        return sum(1 for p in l.split("+")
                   if "_" in p and not p.startswith("Vac") and not p.endswith("_i")
                   and role(p.split("_")[0]) == role(p.split("_")[1]))

    best = max(score(l) for l in labels)
    top = [l for l in labels if score(l) == best]
    return (top[0], False) if len(top) == 1 else (None, True)


def geometry_decisions():
    """contested_geometry.json -> {row key: chosen label}. The vacancy's occupants are the
    len(vac) added atoms CLOSEST to a vacancy site; a decision requires the last occupant
    within 1.7 A and a clear gap (>=0.3 A) to the first interstitial. CdSe0.12Te0.88 sits
    inside that rule (1.01/1.65 and 1.09/1.58 A); everything looser is left contested."""
    decided = {}
    geo = json.loads((PROV / "contested_geometry.json").read_text())
    for g in geo:
        if "error" in g or not g.get("vac"):
            continue
        assign = sorted((a for a in g["assign"] if a["dist"] is not None),
                        key=lambda a: a["dist"])
        nvac = len(g["vac"])
        if len(assign) <= nvac:
            continue
        on_site, off_site = assign[:nvac], assign[nvac:]
        if on_site[-1]["dist"] >= 1.7 or off_site[0]["dist"] < on_site[-1]["dist"] + 0.3:
            continue
        parts = [f"{a['added']}_{a['nearest_site']}" for a in on_site]
        parts += [f"{a['added']}_i" for a in off_site]
        def rank(p):
            return (0 if p.startswith("Vac_") else (2 if p.endswith("_i") else 1), p)
        label = "+".join(sorted(parts, key=rank))
        # the geometry answer must be one of the dn-legal labels
        if label in g["alts"]:
            th = FK[g["row"].split("|")[0]]
            rest = g["row"].split("|", 1)[1]
            decided[f"{th}|{rest}"] = label
    return decided


def main() -> None:
    audit = json.loads((PROV / "audit_dn_mismatch.json").read_text())["label_mismatch"]
    data = json.loads(DATA.read_text())
    rows = {f"{r['f']}|{r['h']}|{r['d']}": r for r in data["defects"]}

    decided = geometry_decisions()
    renames, pristine, held, already = {}, [], [], 0
    for key, dn, _exp in audit:
        th, host, defect = key.split("|")
        kk = f"{FK[th]}|{host}|{defect}"
        if kk in HELD:
            held.append(kk)
            continue
        if kk not in rows:
            already += 1  # a previous run of this script already moved this row
            continue
        # A previous run may have renamed a DIFFERENT row onto this key (swap). The key
        # then belongs to that row now, not to the audited cell -- tell them apart by dn.
        row_dn = {e: v for e, v in
                  ((e, round(v)) for e, v in (rows[kk].get("dn") or {}).items()) if v}
        if row_dn != {e: round(v) for e, v in dn.items()}:
            already += 1
            continue
        if not dn:
            pristine.append(kk)
            continue
        if kk in decided:
            renames[kk] = decided[kk]
            continue
        label, contested = preferred_label({e: round(v) for e, v in dn.items()}, defect)
        if contested:
            held.append(kk)
            continue
        renames[kk] = label

    # the 7 complex_ labels the audit could not parse: dn decides these too
    for r in data["defects"]:
        kk = f"{r['f']}|{r['h']}|{r['d']}"
        if not r["d"].startswith("complex_") or kk in renames or kk in HELD:
            continue
        rd = {e: round(v) for e, v in (r.get("dn") or {}).items()}
        if not rd:
            pristine.append(kk)
            continue
        label, contested = preferred_label(rd, "")
        if contested:
            held.append(kk)
            continue
        renames[kk] = label

    # collision numbering on the FINAL label set: one configuration bare, more than one
    # numbered 1..N (tree rule). A withheld row frees its label.
    final = {}
    for r in data["defects"]:
        kk = f"{r['f']}|{r['h']}|{r['d']}"
        if kk in pristine:
            continue
        nl = renames.get(kk, r["d"])
        final.setdefault(f"{r['f']}|{r['h']}|{nl}", []).append(kk)
    for nk, members in final.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda kk: (kk in renames, kk))  # already-correct labels first
        for i, kk in enumerate(members, 1):
            base = nk.split("|", 2)[2]
            renames[kk] = f"{base}-{i}"

    if not renames and not pristine:
        print(f"nothing to do -- labels already match cells ({already} audit keys already moved)")
        return

    # self-audit: every new label must parse back to exactly the cell's dn
    for kk, nl in renames.items():
        stem = nl.rsplit("-", 1)
        base = stem[0] if len(stem) == 2 and stem[1].isdigit() else nl
        rd = {e: round(v) for e, v in rows[kk].get("dn", {}).items()}
        rd = {e: v for e, v in rd.items() if v}
        if label_dn(base) != rd:
            sys.exit(f"self-audit failed: {kk} -> {nl} parses to {label_dn(base)}, cell is {rd}")

    record = []
    for kk, nl in sorted(renames.items()):
        r = rows[kk]
        old = r["d"]
        if old == nl:
            continue
        record.append({"key": kk, "old": old, "new": nl,
                       "dn": {e: round(v) for e, v in r.get("dn", {}).items()}})
    for kk in pristine:
        record.append({"key": kk, "old": rows[kk]["d"], "new": None,
                       "note": "cell is pristine (dn = {}); not a defect -- withheld"})

    # Asset keys embed the label: trajs are f__h__d, DOS adds __q. Build the full key map
    # BEFORE touching anything on disk.
    keymap = {}
    for rec in record:
        if not rec["new"]:
            continue
        f, h = rec["key"].split("|")[:2]
        old_base, new_base = f"{f}__{h}__{rec['old']}", f"{f}__{h}__{rec['new']}"
        keymap[old_base] = new_base                      # traj key
        for k in data.get("dosKeys", []):                # dos keys carry the charge suffix
            if k.startswith(old_base + "__"):
                keymap[k] = new_base + k[len(old_base):]

    # Two hazards, both handled per the tree's own lessons (provenance/README.md):
    #  * label SWAPS (Se_Te <-> Te_Se): every rename goes through a temp name, so a swap
    #    can never clobber its counterpart -- the file follows its row;
    #  * a file already sitting at the target name with NO row claiming it (dangling key --
    #    e.g. a Vac_Ga trajectory whose row never shipped): that is a different cell's movie,
    #    and leaving it would show it under the renamed row, so the orphan is parked aside
    #    as <name>__orphan and kept in the repo as evidence.
    live_old_keys = set()
    for r in data["defects"]:
        live_old_keys.add(f"{r['f']}__{r['h']}__{r['d']}")
        for k in (r.get("dos") or {}).values():
            live_old_keys.add(k)
    orphans = []
    for sub, ext in (("trajs", ".json.gz"), ("dos", ".json.gz")):
        folder = REPO / "docs" / sub
        targets = {}
        for old_k, new_k in keymap.items():
            dst = folder / f"{new_k}{ext}"
            if dst.is_file() and new_k not in keymap:   # not a swap partner -> orphan
                if new_k in live_old_keys:
                    sys.exit(f"target {new_k} is a live unrenamed row's asset -- "
                             "collision numbering failed; refusing to park it")
                targets[new_k] = dst
        for new_k, dst in targets.items():
            parked = folder / f"{new_k}__orphan{ext}"
            n = 2
            while parked.exists():
                parked = folder / f"{new_k}__orphan{n}{ext}"
                n += 1
            dst.rename(parked)
            orphans.append({"file": f"{sub}/{new_k}{ext}", "parked_as": parked.name})
        temp = {}
        for old_k, new_k in sorted(keymap.items()):
            src = folder / f"{old_k}{ext}"
            if src.is_file():
                t = folder / f"{old_k}__relabel_tmp{ext}"
                src.rename(t)
                temp[old_k] = (t, folder / f"{new_k}{ext}")
        for old_k, (t, dst) in temp.items():
            if dst.exists():
                sys.exit(f"rename would clobber even after parking: {dst}")
            t.rename(dst)

    # only now mutate the payload
    for rec in record:
        if not rec["new"]:
            continue
        r = rows[rec["key"]]
        r["d"] = rec["new"]
        if r.get("dos"):
            f, h = rec["key"].split("|")[:2]
            old_base = f"{f}__{h}__{rec['old']}"
            r["dos"] = {q: keymap.get(k, k) for q, k in r["dos"].items()}
    gone = {r["key"] for r in record if not r["new"]}
    data["defects"] = [r for r in data["defects"]
                       if f"{r['f']}|{r['h']}|{r['d']}" not in gone]
    for field in ("trajKeys", "dosKeys"):
        if field in data:
            data[field] = [keymap.get(k, k) for k in data[field]]

    DATA.write_text(json.dumps(data, separators=(",", ":")))
    # re-runs merge into the existing record instead of overwriting it
    prior = {"renamed": [], "withheld_pristine": [], "held": [], "orphans_parked": []}
    if (PROV / "defect_relabels.json").is_file():
        prior.update(json.loads((PROV / "defect_relabels.json").read_text()))
    prior["renamed"].extend(r for r in record if r["new"])
    prior["withheld_pristine"].extend(r for r in record if not r["new"])
    prior["held"] = sorted(set(prior["held"]) | set(held))
    prior["orphans_parked"].extend(orphans)
    (PROV / "defect_relabels.json").write_text(json.dumps(prior, indent=1))
    print(f"renamed {sum(1 for r in record if r['new'])} labels, "
          f"withheld {len(pristine)} pristine cells, held {len(set(held))} contested rows, "
          f"parked {len(orphans)} orphan files")
    print(f"wrote {PROV / 'defect_relabels.json'}")


if __name__ == "__main__":
    main()
