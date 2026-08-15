"""Benchmark the raw-derived defect pipeline against the campaign's own validated CSV.

The CSV (cdsete_defect_library_generation_pbesol.csv) is the number the shipped site quotes:
per defect it carries Toten_pure, Toten_{p2,p1,neut,m1,m2}, Corr_*, VBM, gap and the summed
chemical-potential term at the Cd-rich and Te-rich limits. If the raw tree reproduces those,
the extraction is sound and only the correction scheme is open. Where it does NOT reproduce
them, the difference is the finding -- it is not smoothed over.
"""
import os, re, gzip, json, sys

B = "/eagle/wbg_defects/chalcogenide_defects"


def opentext(path):
    """every file in the defect tree is gzipped; the bulk tree is mixed"""
    if os.path.exists(path):
        return open(path, "r", errors="ignore")
    if os.path.exists(path + ".gz"):
        return gzip.open(path + ".gz", "rt", errors="ignore")
    return None


def last_F(d):
    """final 'F=' from OSZICAR. float() the token because VASP writes -.169E+04."""
    fh = opentext(f"{d}/OSZICAR")
    if not fh:
        return None, None
    F = E0 = None
    with fh:
        for line in fh:
            if " F= " in line:
                t = line.split()
                try:
                    F = float(t[t.index("F=") + 1])
                    E0 = float(t[t.index("E0=") + 1])
                except (ValueError, IndexError):
                    pass
    return F, E0


def lattice(d):
    fh = opentext(f"{d}/CONTCAR") or opentext(f"{d}/POSCAR")
    if not fh:
        return None
    with fh:
        ls = [next(fh) for _ in range(8)]
    s = float(ls[1].split()[0])
    v = [[float(x) * s for x in ls[i].split()] for i in (2, 3, 4)]
    return [round(sum(c * c for c in r) ** 0.5, 6) for r in v]


def incar(d):
    fh = opentext(f"{d}/INCAR")
    if not fh:
        return {}
    out = {}
    with fh:
        for line in fh:
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                out[k.strip().upper()] = v.split("#")[0].strip()
    return out


def nelect(d):
    """NELECT actually used, from OUTCAR -- the electron count IS the charge state (gate 3)"""
    fh = opentext(f"{d}/OUTCAR")
    if not fh:
        return None
    with fh:
        for line in fh:
            if "NELECT" in line:
                m = re.search(r"NELECT\s*=\s*([-\d.]+)", line)
                if m:
                    return float(m.group(1))
    return None


HOST = f"{B}/DFT/defect/PBEsol/CdTe"
print("=== candidate pristine references for PBEsol CdTe")
for d in [f"{B}/DFT/bulk/PBEsol/CdTe/216_atoms", f"{B}/DFT/bulk/PBEsol/CdTe",
          f"{B}/DFT/bulk/PBEsol/CdTe/8_atoms"]:
    F, E0 = last_F(d)
    if F is None:
        continue
    ic = incar(d)
    print(f"  {d.replace(B + '/', ''):42s} F={F:14.5f} E0={E0:14.5f} "
          f"ISIF={ic.get('ISIF')} NSW={ic.get('NSW')} abc={lattice(d)}")

print("\n=== defect energies, raw vs CSV (CSV values quoted in the last columns)")
CSV = {  # AB=CdTe rows, simple defects, straight from the shipped csv
    "As_Te":  dict(pure=-592.22, p2=-587.29, p1=-589.87, neut=-592.40, m1=-594.29, m2=-595.68,
                   cp2=0.29, cp1=0.01, cm1=0.06, cm2=0.23, vbm=2.14, gap=0.64),
    "Cd_Te":  dict(pure=-592.22, neut=-587.25, cp1=0.10, vbm=2.14, gap=0.64),
    "Cd_i":   dict(pure=-592.22, neut=-592.40, cp1=0.14, vbm=2.14, gap=0.64),
    "Cl_Te":  dict(pure=-592.22, neut=-591.06, cp1=0.07, vbm=2.14, gap=0.64),
}
for name in sorted(os.listdir(HOST)):
    if name not in CSV:
        continue
    print(f"  {name}")
    for c in ("Charged+2", "Charged+1", "Neutral", "Charged-1", "Charged-2"):
        d = f"{HOST}/{name}/{c}"
        if not os.path.isdir(d):
            continue
        F, E0 = last_F(d)
        ne = nelect(d)
        ic = incar(d)
        print(f"    {c:11s} F={F if F is None else round(F, 5)!s:>13s} "
              f"NELECT={ne} ISIF={ic.get('ISIF')} abc={lattice(d)}")
