const PORT=9333, BASE=process.argv[2]||"http://127.0.0.1:8877/index.html";
const nt=await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`,{method:"PUT"})).json();
const ws=new WebSocket(nt.webSocketDebuggerUrl); await new Promise(r=>ws.onopen=r);
let id=0; const waiters=new Map();
ws.onmessage=m=>{const d=JSON.parse(m.data); if(d.id&&waiters.has(d.id)){waiters.get(d.id)(d);waiters.delete(d.id);}};
const send=(m2,p={})=>new Promise(res=>{const i=++id;waiters.set(i,res);ws.send(JSON.stringify({id:i,method:m2,params:p}))});
const evalJS=async e=>{const r=await send("Runtime.evaluate",{expression:e,awaitPromise:true,returnByValue:true});
  return r.result?.exceptionDetails?{__err:String(JSON.stringify(r.result.exceptionDetails)).slice(0,300)}:r.result?.result?.value;};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
await send("Page.enable"); await send("Network.enable");
await send("Network.clearBrowserCache"); await send("Network.setCacheDisabled",{cacheDisabled:true});
await send("Page.navigate",{url:BASE+"?b="+Date.now()});
for(let i=0;i<120;i++){await sleep(500); if(await evalJS("(()=>{try{return DEFECTS.length}catch(e){return 0}})()"))break;}
const out=await evalJS(`(async()=>{
  const res={};
  // 1. Vac_Ba: q=-2 withheld with the level-below-VBM reason, others intact
  const b=DEFECTS.find(r=>r.h==="Cu1.5Ag0.5Ba1Sn1S4_stannite"&&r.d==="Vac_Ba");
  const bq=b.vx["S-rich / Ba-poor"].q;
  res.vacBa={m2:bq["-2"].vbm, m2note:(bq["-2"].note||"").includes("below the VBM"), m1:bq["-1"].vbm, n:bq["0"].vbm};
  // 2. In_Ag AgInSSe ord1: spy on sgShow to capture nparts for the MAIN window
  const r2=DEFECTS.find(r=>r.h==="Ag1In1S1Se1_kesterite"&&r.d==="In_Ag");
  const orig=window.sgShow; let captured=[];
  window.sgShow=(el,o)=>{captured.push({nparts:o.nparts,hasBulk:!!o.bulkCif});return orig(el,o);};
  dOpenDetail(r2); await new Promise(x=>setTimeout(x,3500));
  window.sgShow=orig;
  res.inAg={nparts:captured.length?captured[captured.length-1].nparts:null,calls:captured.length,
            head:(document.getElementById("dstructhead")||{}).textContent||""};
  closeModals();
  // 3. control Vac (ring) still nparts 1: Vac_S in same host family
  const r3=DEFECTS.find(r=>r.d.startsWith("Vac_")&&r.h==="Ag1In1S1Se1_kesterite");
  if(r3){captured=[];window.sgShow=(el,o)=>{captured.push(o.nparts);return orig(el,o);};
    dOpenDetail(r3); await new Promise(x=>setTimeout(x,3000)); window.sgShow=orig;
    res.vacCtl={d:r3.d,nparts:captured.length?captured[captured.length-1]:null}; closeModals();}
  return res;
})()`);
console.log(JSON.stringify(out));
await send("Target.closeTarget",{targetId:nt.id}).catch(()=>{}); ws.close();
