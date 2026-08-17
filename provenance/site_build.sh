#!/bin/bash
# Canonical site build + publish, all on Eagle (user directive 2026-08-17: nothing on
# Gautschi except running DFT; push from Eagle always).
# Steps: derived data -> audits -> marks -> payload -> assemble repo docs -> build -> push.
set -e
B=/eagle/wbg_defects/materialsHUB/telluride
L=$B/log
R=$B/site/repo
cd $L
python3 build_all.py
python3 audit_dn.py
python3 gen_marks.py
# the two big dos_defect jsonls killed the login node once; split anything >150MB first
for f in dos_defect_*.jsonl; do
  sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
  if [ "$sz" -gt 157286400 ] && [[ "$f" != *part* ]]; then
    split -C 150m -d --additional-suffix=.jsonl "$f" "${f%.jsonl}_part" && mv "$f" "$f.whole"
  fi
done
python3 build_payload_eagle.py
# assemble into the repo checkout
python3 - <<'PY'
import json, os, tarfile, shutil
L = "/eagle/wbg_defects/materialsHUB/telluride/log"
R = "/eagle/wbg_defects/materialsHUB/telluride/site/repo"
d = json.load(open(f"{L}/payload/data.json"))
dm = json.load(open(f"{L}/dmarks.json"))
THR = {"hse": "HSE", "hse_soc": "HSE+SOC", "pbe": "PBE", "pbe_u": "PBE+U", "pbesol": "PBEsol"}
for r in d["defects"]:
    m = dm.get(f"{THR[r['f']]}|{r['h']}|{r['d']}")
    if m:
        if m.get("mk") is not None: r["mk"], r["vc"] = m["mk"], m.get("vc", [])
        if m.get("why"): r["mkwhy"] = m["why"]
# fresh dos extraction so files and keys can never drift apart
with tarfile.open(f"{L}/payload/dos.tar") as tf: tf.extractall(R + "/docs")
for sub, ext, field in (("trajs", ".json.gz", "trajKeys"), ("dos", ".json.gz", "dosKeys")):
    d[field] = sorted(f[:-len(ext)] for f in os.listdir(f"{R}/docs/{sub}") if f.endswith(ext))
json.dump(d, open(f"{R}/docs/data.json", "w"), separators=(",", ":"))
shutil.copy(f"{L}/payload/optics.json.gz", f"{R}/docs/optics.json.gz")
shutil.copy(f"{L}/payload/chempot.json.gz", f"{R}/docs/chempot.json.gz")
print("repo docs assembled")
PY
cd $R
python3 site_src/build_site.py
git add -A
git commit -m "site build from Eagle: $(date +%F)" || echo "nothing to commit"
git push origin main
echo "PUSHED FROM EAGLE: $(grep -o 'build [0-9a-f]\{12\}' docs/index.html | head -1)"
