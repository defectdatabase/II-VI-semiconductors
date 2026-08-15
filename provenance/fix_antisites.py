"""Verify, then swap, the antisite directory labels that contradict their own cells.

Renaming is what created this class of error in the first place, so nothing moves until BOTH
independent routes agree on the same dn for the same directory:

  route 1  composition of the defect CONTCAR minus the pristine supercell CONTCAR
  route 2  NELECT from the defect OUTCAR minus the pristine's, decomposed over the PAW ZVALs

The pristine is the bulk run whose LATTICE matches the defect cells (gate 2), not whichever
bulk directory happens to carry the host's name -- for CdTe those two differ by 0.84 eV.

Pass --apply to perform the swap; the default is a dry run.
"""
import os, re, gzip, sys, json, collections

B = "/eagle/wbg_defects/chalcogenide_defects"
APPLY = "--apply" in sys.argv


def op(p):
    if os.path.exists(p):
        return open(p, errors="ignore")
    if os.path.exists(p + ".gz"):
        return gzip.open(p + ".gz", "rt", errors="ignore")
    return None


def head(d, n=8):
    fh = op(f"{d}/CONTCAR") or op(f"{d}/POSCAR")
    if not fh:
        return None
    try:
        return [fh.readline() for _ in range(n)]
    finally:
        fh.close()


def comp(d):
    ls = head(d)
    if not ls:
        return None
    try:
        return dict(zip(ls[5].split(), [int(x) for x in ls[6].split()]))
    except (ValueError, IndexError):
        return None


def abc(d):
    ls = head(d)
    if not ls:
        return None
    try:
        s = float(ls[1].split()[0])
        v = [[float(x) * s for x in ls[i].split()] for i in (2, 3, 4)]
    except (ValueError, IndexError):
        return None
    return tuple(round(sum(c * c for c in r) ** 0.5, 3) for r in v)


def nelect_zval(d):
    fh = op(f"{d}/OUTCAR")
    if not fh:
        return None, None
    ne, zv = None, []
    try:
        for i, line in enumerate(fh):
            if ne is None and "NELECT" in line:
                m = re.search(r"NELECT\s*=\s*([-\d.]+)", line)
                if m:
                    ne = float(m.group(1))
            if "ZVAL   =" in line:
                zv += [float(x) for x in re.findall(r"ZVAL\s*=\s*([\d.]+)", line)]
            if ne is not None and zv and i > 3000:
                break
    finally:
        fh.close()
    return ne, zv


def species_order(d):
    ls = head(d)
    return ls[5].split() if ls else []


def find_pristine(theory, host, target_abc):
    """the bulk run for this host whose cell matches the defect cells"""
    root = f"{B}/DFT/bulk/{theory}"
    cands = []
    for name in os.listdir(root):
        if not name.split("_")[0] == host.split("_")[0] and host not in name:
            continue
        base = f"{root}/{name}"
        for d in [base] + [f"{base}/{s}" for s in (os.listdir(base) if os.path.isdir(base) else [])
                           if os.path.isdir(f"{base}/{s}")]:
            a = abc(d)
            if a and target_abc and max(abs(x - y) for x, y in zip(a, target_abc)) < 0.01:
                cands.append(d)
    return cands


swaps = json.load(open(f"{B}/log/antisite_swaps.json"))
print(f"{len(swaps)} candidate swaps\n")
confirmed = []
for s in swaps:
    th, host, dname = s["theory"], s["host"], s["dir"]
    dp = f"{B}/DFT/defect/{th}/{host}/{dname}"
    subs = [c for c in sorted(os.listdir(dp)) if os.path.isdir(f"{dp}/{c}")]
    neutral = "Neutral" if "Neutral" in subs else subs[0]
    cd = f"{dp}/{neutral}"
    dc, da = comp(cd), abc(cd)
    pcands = find_pristine(th, host, da)
    if not pcands:
        print(f"  SKIP {th}/{host}/{dname}: no cell-matched pristine")
        continue
    pc = comp(pcands[0])
    if not pc or not dc:
        print(f"  SKIP {th}/{host}/{dname}: unreadable composition")
        continue
    dn = {e: dc.get(e, 0) - pc.get(e, 0) for e in set(dc) | set(pc)}
    dn = {e: v for e, v in dn.items() if v}
    add = [e for e, v in dn.items() if v > 0]
    rem = [e for e, v in dn.items() if v < 0]
    if not (len(add) == 1 and len(rem) == 1 and dn[add[0]] == 1 and dn[rem[0]] == -1):
        print(f"  SKIP {th}/{host}/{dname}: dn={dn} is not a simple antisite")
        continue
    correct = f"{add[0]}_{rem[0]}"
    # route 2: the electron count must move by the same swap
    ne, zv = nelect_zval(cd)
    order = species_order(cd)
    z = dict(zip(order, zv)) if zv and len(zv) >= len(order) else {}
    ok2 = None
    if ne is not None and z and neutral == "Neutral":
        pne, pzv = nelect_zval(pcands[0])
        if pne is not None:
            pred = pne + z.get(add[0], 0) - z.get(rem[0], 0)
            ok2 = abs(pred - ne) < 1e-6
    print(f"  {th}/{host}/{dname:10s} -> {correct:10s} dn={dn} "
          f"pristine={pcands[0].replace(B + '/', '')} NELECT_check={ok2}")
    if correct != dname:
        confirmed.append((f"{B}/DFT/defect/{th}/{host}", dname, correct, ok2))

print(f"\nconfirmed renames: {len(confirmed)}")
if not APPLY:
    print("dry run -- pass --apply to perform the swaps")
    sys.exit()

# group by parent so a two-way swap can go through a temp name
byparent = collections.defaultdict(list)
for parent, old, new, _ in confirmed:
    byparent[parent].append((old, new))
done = 0
for parent, pairs in byparent.items():
    tmp = {}
    for old, new in pairs:
        t = f"{old}__swaptmp"
        os.rename(f"{parent}/{old}", f"{parent}/{t}")
        tmp[t] = new
    for t, new in tmp.items():
        dst = f"{parent}/{new}"
        if os.path.exists(dst):
            print(f"  COLLISION {dst} already exists; leaving {t} in place")
            continue
        os.rename(f"{parent}/{t}", dst)
        done += 1
print(f"renamed {done}")
