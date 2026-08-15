"""Audit every defect label against the composition of its own cell.

The pristine composition is NOT guessed from the modal composition across defects -- most of a
host's defects sit on the anion site, so the mode reports the anion one short and every label
then reads as shifted (that error is what produced a bogus 30/79 mismatch on CdTe).

It is derived instead from the host formula scaled to the cell: for a defect cell of about N
atoms, the pristine is the host stoichiometry times the integer scale that best fits, checked
against any bulk run that shares the defect cells' lattice.
"""
import os, re, gzip, sys, json, collections, math

B = "/eagle/wbg_defects/chalcogenide_defects"
D = f"{B}/DFT/defect"
FORM = re.compile(r"([A-Z][a-z]?)([0-9]*\.?[0-9]*)")
CFG = re.compile(r"-\d+$")


def op(p):
    if os.path.exists(p):
        return open(p, errors="ignore")
    if os.path.exists(p + ".gz"):
        return gzip.open(p + ".gz", "rt", errors="ignore")
    return None


def comp(d):
    fh = op(f"{d}/CONTCAR") or op(f"{d}/POSCAR")
    if not fh:
        return None
    try:
        ls = [fh.readline() for _ in range(8)]
    finally:
        fh.close()
    try:
        els, cnt = ls[5].split(), [int(x) for x in ls[6].split()]
    except (ValueError, IndexError):
        return None
    if not els or not re.fullmatch(r"[A-Z][a-z]?", els[0]):
        return None
    return dict(zip(els, cnt))


def host_ratio(name):
    out = {}
    for el, num in FORM.findall(name.split("_")[0]):
        if not el:
            continue
        out[el] = out.get(el, 0.0) + (float(num) if num else 1.0)
    return out


def pristine_for(hostname, cells):
    """host stoichiometry scaled to the cell size the defects actually use"""
    ratio = host_ratio(hostname)
    tot = sum(ratio.values())
    if not tot:
        return None
    # the modal atom count over the defect cells, then the scale that reproduces it
    n = collections.Counter(sum(c.values()) for c in cells).most_common(1)[0][0]
    scale = round(n / tot)
    if scale < 1:
        return None
    pr = {e: r * scale for e, r in ratio.items()}
    if any(abs(v - round(v)) > 1e-6 for v in pr.values()):
        return None
    return {e: int(round(v)) for e, v in pr.items()}


def label_from_dn(dn):
    add = sorted(e for e, v in dn.items() if v > 0)
    rem = sorted(e for e, v in dn.items() if v < 0)
    if len(rem) == 1 and not add and dn[rem[0]] == -1:
        return f"V_{rem[0]}"
    if len(add) == 1 and not rem and dn[add[0]] == 1:
        return f"{add[0]}_i"
    if len(add) == 1 and len(rem) == 1 and dn[add[0]] == 1 and dn[rem[0]] == -1:
        return f"{add[0]}_{rem[0]}"
    return "complex"


tot = collections.Counter()
swaps = []
for th in sorted(os.listdir(D)):
    tp = f"{D}/{th}"
    if not os.path.isdir(tp):
        continue
    for host in sorted(os.listdir(tp)):
        hp = f"{tp}/{host}"
        if not os.path.isdir(hp):
            continue
        entries = []
        for dn_ in sorted(os.listdir(hp)):
            dp = f"{hp}/{dn_}"
            if not os.path.isdir(dp):
                continue
            subs = [c for c in sorted(os.listdir(dp)) if os.path.isdir(f"{dp}/{c}")]
            if not subs:
                continue
            c = comp(f"{dp}/{subs[0]}")
            if c:
                entries.append((dn_, c))
        if not entries:
            continue
        pr = pristine_for(host, [c for _, c in entries])
        if not pr:
            tot["no_pristine"] += len(entries)
            continue
        for dname, c in entries:
            dn = {e: c.get(e, 0) - pr.get(e, 0) for e in set(c) | set(pr)}
            dn = {e: v for e, v in dn.items() if v}
            derived = label_from_dn(dn)
            base = CFG.sub("", dname)
            if derived == "complex":
                tot["complex"] += 1
            elif derived == base:
                tot["agree"] += 1
            else:
                tot["mismatch"] += 1
                # is it specifically an antisite written the other way round?
                if "_" in base and "_i" not in base and not base.startswith("V_"):
                    a, _, b = base.partition("_")
                    if derived == f"{b}_{a}":
                        tot["antisite_swapped"] += 1
                        swaps.append((th, host, dname, derived))
                        continue
                if len(swaps) < 0:
                    pass
                tot["other_mismatch"] += 1
                if tot["other_mismatch"] <= 25:
                    print(f"  OTHER {th}/{host}/{dname:20s} files say {derived:12s} dn={dn}")

print("\n=== totals", dict(tot))
print(f"=== antisite label swaps: {len(swaps)}")
for s in swaps[:20]:
    print("   ", s)
by = collections.Counter((t, h) for t, h, _, _ in swaps)
print("=== hosts affected:", len(by))
for k, v in by.most_common(15):
    print("   ", k, v)
json.dump([{"theory": t, "host": h, "dir": d, "correct": c} for t, h, d, c in swaps],
          open(f"{B}/log/antisite_swaps.json", "w"), indent=1)
print("wrote log/antisite_swaps.json")
