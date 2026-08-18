import json,glob,re,collections,math
LOG="/scratch/gautschi/rahma103/mhub_build/log"
def foot(inc):
    if isinstance(inc,list): inc="\n".join(map(str,inc))
    if isinstance(inc,dict): inc=" ".join(f"{a}={v}" for a,v in inc.items())
    inc=inc or ""
    def g(t):
        m=re.search(rf"\b{t}\s*=\s*([^\s;]+)",inc,re.I); return m.group(1) if m else None
    T=lambda v: bool(v) and v.strip(".").upper().startswith("T")
    hf=T(g("LHFCALC")); soc=T(g("LSORBIT")); u=T(g("LDAU")); gga=(g("GGA") or "").upper()
    base = "PBEsol" if gga=="PS" else ("PBE" if gga in ("","PE") else gga)
    f = ("HSE/"+base) if hf else base
    if soc: f+="+SOC"
    if u: f+="+U"
    return f, g("ENCUT")
LABEL2CLASS={"PBE":{"PBE"},"PBE+U":{"PBE+U"},"PBEsol":{"PBEsol"},"HSE":{"HSE/PBE","HSE/PBEsol"},"HSE+SOC":{"HSE/PBEsol+SOC","HSE/PBE+SOC"}}
recs=collections.defaultdict(list); seen=set()
for fn in sorted(glob.glob(f"{LOG}/steps_bulk_*.jsonl")):
    for line in open(fn):
        d=json.loads(line)
        k=(d.get("theory"),d.get("compound"),d.get("variant"))
        if k in seen or d.get("F") is None: continue
        seen.add(k)
        m=re.match(r"(\d+)_atoms",d.get("variant") or "")
        nat=int(m.group(1)) if m else None
        f,enc=foot(d.get("incar"))
        recs[(d["theory"],d["compound"])].append({"F":d["F"],"nat":nat,"cls":f,"enc":enc,"var":d.get("variant"),"conv":d.get("force_converged")})
b=json.load(open(f"{LOG}/derived_bulk.json"))
cat=collections.Counter(); ex=collections.defaultdict(list)
for k,r in b.items():
    rs=recs.get((r["theory"],r["compound"]),[])
    match=[x for x in rs if abs(x["F"]-r["F"])<0.02] if r.get("F") is not None else []
    ok=LABEL2CLASS.get(r["theory"],set())
    if match:
        c=match[0]["cls"]
        if c in ok: cat[(r["theory"],"a:matched-ok",c)]+=1
        else: cat[(r["theory"],"b:matched-MISLABEL",c)]+=1; ex[(r["theory"],"b",c)].append(r["compound"])
    else:
        same=[x for x in rs if x["cls"] in ok]
        if same: cat[(r["theory"],"c:unmatched-sameclass-exists")]+=1; ex[(r["theory"],"c")].append((r["compound"],r["F"],[(x["F"],x["cls"],x["var"]) for x in rs][:4]))
        elif rs: cat[(r["theory"],"d:unmatched-only-otherclass")]+=1; ex[(r["theory"],"d")].append((r["compound"],r["F"],[(x["F"],x["cls"],x["var"]) for x in rs][:4]))
        else: cat[(r["theory"],"e:no-record")]+=1; ex[(r["theory"],"e")].append(r["compound"])
for k,v in sorted(cat.items()): print(k,v)
for k,v in ex.items(): print("EX",k,len(v),v[:6])
# sanity: positive F_per_atom or |Ef|>3.5
bad=[(k,r["F_per_atom"],r["Ef_per_atom"]) for k,r in b.items() if r.get("F_per_atom") is not None and (r["F_per_atom"]>0 or (r.get("Ef_per_atom") is not None and abs(r["Ef_per_atom"])>3.5))]
print("unphysical energies:",len(bad),bad[:10])
