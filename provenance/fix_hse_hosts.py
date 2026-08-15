"""Repair the 132 malformed HSE defect hosts.

Cause: the Cd-Zn-X source name is `defect-<host>_single_<defect>_<sym>_<fingerprint>_0[-cfg]`,
and the filer split it on the FIRST DASH and then stripped underscores from the host token. The
host therefore swallowed the whole descriptor: `Cd0.50Zn0.50Te_single_Te_Zn_C1_Te2.67...` became
the single directory name `Cd0.50Zn0.50TesingleTeZnC1Te2.67Te2.71Zn4.400`.

The mangled string is NOT un-mangled by guessing where the underscores were -- that is unrecoverable
in general (`AsCdC1...` is As_Cd or A_sCd). The host is taken as the formula before `single`, and
the DEFECT IS RE-DERIVED FROM COMPOSITION against that host's pristine, which is the standing rule.

Layout found: <mangled-host>/<config-index>/<charge>/  ->  <host>/<defect>-<cfg>/<charge>/
"""
import os, re, sys, gzip, json, math, collections
B = "/eagle/wbg_defects/chalcogenide_defects"
APPLY = "--apply" in sys.argv
FORM = re.compile(r"([A-Z][a-z]?)([0-9]*\.?[0-9]*)")
st = collections.Counter(); plan = []

def op(p):
    if os.path.exists(p): return open(p, errors="ignore")
    if os.path.exists(p+".gz"): return gzip.open(p+".gz","rt",errors="ignore")
def comp_of(d):
    fh = op(f"{d}/CONTCAR") or op(f"{d}/POSCAR")
    if not fh: return None
    ls=[fh.readline() for _ in range(7)]; fh.close()
    try: els, cnt = ls[5].split(), [int(x) for x in ls[6].split()]
    except Exception: return None
    if not els or not re.fullmatch(r"[A-Z][a-z]?", els[0]): return None
    c={}
    for e,n in zip(els,cnt): c[e]=c.get(e,0)+n     # SUM repeated blocks
    return c
def host_ratio(name):
    out={}
    for el,num in FORM.findall(name):
        if el: out[el]=out.get(el,0.0)+(float(num) if num else 1.0)
    return out
def label(dn):
    add=sorted(e for e,v in dn.items() if v>0); rem=sorted(e for e,v in dn.items() if v<0)
    if len(rem)==1 and not add and dn[rem[0]]==-1: return f"V_{rem[0]}"
    if len(add)==1 and not rem and dn[add[0]]==1: return f"{add[0]}_i"
    if len(add)==1 and len(rem)==1 and dn[add[0]]==1 and dn[rem[0]]==-1: return f"{add[0]}_{rem[0]}"
    return None

root=f"{B}/DFT/defect/HSE"
known=[h for h in os.listdir(root) if "single" not in h and os.path.isdir(f"{root}/{h}")]
known.sort(key=len, reverse=True)
for name in sorted(os.listdir(root)):
    if "single" not in name: continue
    d=f"{root}/{name}"
    if not os.path.isdir(d): continue
    host=name.split("single")[0]
    ratio=host_ratio(host); tot=sum(ratio.values())
    if not tot: st["no_host"]+=1; continue
    for cfg in sorted(os.listdir(d)):
        cd=f"{d}/{cfg}"
        if not os.path.isdir(cd): continue
        for ch in sorted(os.listdir(cd)):
            src=f"{cd}/{ch}"
            if not os.path.isdir(src): continue
            c=comp_of(src)
            if not c: st["no_comp"]+=1; continue
            nat=sum(c.values()); scale=nat/tot
            # the pristine is the host stoichiometry at the nearest integer scale
            best=None
            for s in (round(scale), round(scale)+1, round(scale)-1):
                if s<1: continue
                pr={e: r*s for e,r in ratio.items()}
                if any(abs(v-round(v))>1e-6 for v in pr.values()): continue
                pr={e:int(round(v)) for e,v in pr.items()}
                dn={e: c.get(e,0)-pr.get(e,0) for e in set(c)|set(pr)}
                dn={e:v for e,v in dn.items() if v}
                lb=label(dn)
                if lb: best=(lb,dn); break
            if not best: st["unresolved"]+=1; continue
            lb,dn=best
            tgt=f"{root}/{host}/{lb}-{cfg}/{ch}"
            plan.append((src,tgt)); st["move"]+=1
            if APPLY:
                os.makedirs(os.path.dirname(tgt), exist_ok=True)
                if os.path.exists(tgt): st["collision"]+=1
                else: os.rename(src,tgt); st["moved"]+=1
print("planned", len(plan), dict(st))
for s_,t_ in plan[:8]: print("   ", s_.replace(B+"/",""), "->", t_.replace(B+"/",""))
if not APPLY: print("dry run")
