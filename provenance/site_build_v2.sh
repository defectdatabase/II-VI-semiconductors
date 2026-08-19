#!/bin/bash
# Telluride site build v2 (Eagle, post-outage flow, certified 2026-08-19):
# build_payload.py -> splice into site/repo/docs -> commit+push AS THE USER.
# Browser verification (CDP probes from the Mac) remains mandatory before calling anything done.
set -e
T=/eagle/wbg_defects/materialsHUB/telluride
cd $T/log
python3 build_payload.py 2>&1 | tee site_build_v2.log
python3 splice_eagle.py
cd $T/site/repo
git -c user.name=msehabibur -c user.email=rahma103@purdue.edu commit -am "${1:-payload rebuild on Eagle}" && git push origin main
echo "PUSHED FROM EAGLE $(git rev-parse --short=9 HEAD)"
