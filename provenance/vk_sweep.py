"""Recompute band gap, dielectric function, absorption and SLME from RAW output, with vaspkit.

Nothing pre-existing in the run directory is read: ABSORPTION.dat, REAL.in, IMAG.in and SLME.dat
are all regenerated from `vasprun.xml` + `EIGENVAL` + `DOSCAR` in a scratch copy, so a stale
campaign file cannot leak into the published number. The run directory is never written to.

Per run it records
  gap_fundamental, gap_direct, vbm, cbm   vaspkit task 911 (and 719's own gap report)
  eps_xx/yy/zz at omega -> 0              REAL.in row 1, which IS epsilon_1(0)
  alpha(E)                                ABSORPTION.dat
  SLME at 0.5 / 1 / 2 / 5 um, per axis    SLME.dat

Solar spectrum: vaspkit's bundled am1.5G.dat, header "ASTM G173-03 Reference Spectra Derived
from SMARTS v. 2.9.2". Validated on the shipped GaAs_SLME example: 31.4787 % here against the
example's stored 31.4549 % (0.024 pp, a version difference in the stored example).

Usage: vk_sweep.py <shard_index> <n_shards>
"""
import os, re, sys, json, glob, gzip, shutil, subprocess, tempfile

B = "/eagle/wbg_defects/chalcogenide_defects"
VK = f"{B}/software/vaspkit/bin/vaspkit"
LOG = f"{B}/log"
SHARD = int(sys.argv[1]) if len(sys.argv) > 1 else 0
NSHARD = int(sys.argv[2]) if len(sys.argv) > 2 else 1
WANT_T = [0.5, 1.0, 2.0, 5.0]
# crux /tmp is a 1.5 GB tmpfs and a single vasprun.xml can be 500 MB, so staging there fills the
# node after two runs ("No space left on device"). Stage on Eagle instead, one dir per shard.
SCRATCH = f"{B}/log/vk_scratch"
NUM = re.compile(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?")


def stage(src, dst, name, required=False):
    p = f"{src}/{name}"
    if os.path.exists(p):
        shutil.copy(p, f"{dst}/{name}")
        return True
    if os.path.exists(p + ".gz"):
        with gzip.open(p + ".gz", "rb") as a, open(f"{dst}/{name}", "wb") as b:
            shutil.copyfileobj(a, b)
        return True
    return not required


def run_vaspkit(cwd, keys):
    try:
        return subprocess.run([VK], input=keys, text=True, cwd=cwd,
                              capture_output=True, timeout=1800).stdout
    except Exception:
        return ""


def parse_gap(out):
    g = {}
    for line in out.splitlines():
        m = re.search(r"Band Gap \(eV\):\s*([-\d.]+)", line)
        if m:
            g["gap"] = float(m.group(1))
        m = re.search(r"Eigenvalue of VBM \(eV\):\s*([-\d.]+)", line)
        if m:
            g["vbm"] = float(m.group(1))
        m = re.search(r"Eigenvalue of CBM \(eV\):\s*([-\d.]+)", line)
        if m:
            g["cbm"] = float(m.group(1))
        m = re.search(r"Fundamental Gap \(eV\):\s*([-\d.]+)", line)
        if m:
            g["gap_fundamental"] = float(m.group(1))
        m = re.search(r"Direct Allowed Gap \(eV\):\s*([-\d.]+)", line)
        if m:
            g["gap_direct"] = float(m.group(1))
    return g


def first_row(path):
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                if line.lstrip().startswith("#"):
                    continue
                v = NUM.findall(line)
                if len(v) >= 4:
                    return [float(x) for x in v]
    except OSError:
        pass
    return None


def parse_curve(path, cols=4, decimate=6):
    out = []
    try:
        with open(path, errors="ignore") as fh:
            for i, line in enumerate(fh):
                if line.lstrip().startswith("#"):
                    continue
                v = NUM.findall(line)
                if len(v) >= cols and i % decimate == 0:
                    out.append([round(float(v[0]), 4), round(float(v[1]), 4),
                                round(float(v[2]), 4), round(float(v[3]), 4)])
    except OSError:
        return None
    return out or None


def parse_slme(path):
    rows = []
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                if line.lstrip().startswith("#"):
                    continue
                v = line.split()
                if len(v) >= 5:
                    try:
                        rows.append([float(x) for x in v[:5]])
                    except ValueError:
                        pass
    except OSError:
        return None
    if not rows:
        return None
    out = {}
    for t in WANT_T:
        best = min(rows, key=lambda r: abs(r[0] - t))
        if abs(best[0] - t) < 0.02:
            out[str(t)] = {"xx": round(best[1], 4), "yy": round(best[2], 4),
                           "zz": round(best[3], 4), "avg": round(best[4], 4)}
    out["saturated_avg"] = round(rows[-1][4], 4)
    out["max_thickness_um"] = round(rows[-1][0], 3)
    return out


# every bulk run that has a vasprun (the dielectric function lives there)
dirs = set()
for pat in ("DFT/bulk/*/*", "DFT/bulk/*/*/*"):
    for p in glob.glob(f"{B}/{pat}/vasprun.xml") + glob.glob(f"{B}/{pat}/vasprun.xml.gz"):
        dirs.add(os.path.dirname(p))
dirs = sorted(dirs)
mine = [d for i, d in enumerate(dirs) if i % NSHARD == SHARD]
print(f"shard {SHARD}/{NSHARD}: {len(mine)} of {len(dirs)} runs", flush=True)

outpath = f"{LOG}/vk_optics_{SHARD}.jsonl"
done = set()
if os.path.exists(outpath):
    for line in open(outpath):
        try:
            done.add(json.loads(line)["path"])
        except Exception:
            pass

n = 0
with open(outpath, "a") as fh:
    for d in mine:
        rel = d.replace(B + "/", "")
        if rel in done:
            continue
        n += 1
        os.makedirs(f"{SCRATCH}/{SHARD}", exist_ok=True)
        tmp = tempfile.mkdtemp(prefix="vk_", dir=f"{SCRATCH}/{SHARD}")
        try:
            if not stage(d, tmp, "vasprun.xml", required=True):
                continue
            for f in ("INCAR", "POSCAR", "KPOINTS", "EIGENVAL", "DOSCAR"):
                stage(d, tmp, f)
            rec = {"path": rel, "had_doscar": os.path.exists(f"{tmp}/DOSCAR"),
                   "had_eigenval": os.path.exists(f"{tmp}/EIGENVAL")}
            rec.update(parse_gap(run_vaspkit(tmp, "911\n")))
            run_vaspkit(tmp, "711\n1\n")               # optics -> REAL.in, IMAG.in, ABSORPTION
            e0 = first_row(f"{tmp}/REAL.in")
            if e0 and len(e0) >= 4:
                rec["eps_xx"], rec["eps_yy"], rec["eps_zz"] = [round(x, 4) for x in e0[1:4]]
                rec["eps_avg"] = round(sum(e0[1:4]) / 3.0, 4)
            rec["alpha"] = parse_curve(f"{tmp}/ABSORPTION.dat")
            out719 = run_vaspkit(tmp, "719\n1\n")
            rec.update(parse_gap(out719))
            rec["slme"] = parse_slme(f"{tmp}/SLME.dat")
            rec["source"] = "vaspkit 1.5.0 tasks 911/711/719 on raw vasprun.xml"
            fh.write(json.dumps(rec) + "\n")
            if n % 25 == 0:
                fh.flush()
                print(f"  {n} done (last {rel})", flush=True)
        except Exception as e:
            fh.write(json.dumps({"path": rel, "error": str(e)[:200]}) + "\n")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
print(f"shard {SHARD} finished, {n} processed", flush=True)
