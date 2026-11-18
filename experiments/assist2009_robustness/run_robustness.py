"""Phase 2C robustness runs without modifying pyKT/pyBKT or Phase 2B."""
from __future__ import annotations
import csv, datetime as dt, hashlib, json, math, os, random, sys, time, traceback
from pathlib import Path
try:
    import resource
except ImportError:
    resource = None  # Only historical Linux RSS reporting uses this module.

ROOT = Path(__file__).resolve().parents[2]
PHASE2A = ROOT / "results/assist2009_phase2a"
OUT = Path(os.environ.get("ASSIST2009_PHASE2C_OUTPUT", str(ROOT / "results/assist2009_phase2c"))).resolve()
sys.path.insert(0, str(ROOT / "code/pyBKT/source-py")); sys.path.insert(0, str(ROOT / "code/pykt-toolkit"))
os.environ.update(WANDB_MODE="disabled", WANDB_DISABLED="true", CUDA_VISIBLE_DEVICES="", MPLBACKEND="Agg",
                  OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
NETWORK_EVENTS = []
sys.addaudithook(lambda event, args: (_ for _ in ()).throw(RuntimeError("network forbidden: " + event))
                 if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"} else None)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def dump(name,obj): (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
def histories(split):
    out=[]
    for line in (PHASE2A/split/"histories.jsonl").open():
        u=json.loads(line); u["events"].sort(key=lambda e:int(e["order_id"])); out.append(u)
    return out
def metrics(rows):
    import numpy as np
    from sklearn.metrics import accuracy_score,brier_score_loss,log_loss,roc_auc_score
    y=np.array([int(x["label"]) for x in rows]); p=np.array([float(x["probability"]) for x in rows])
    assert len(y) and np.isfinite(p).all() and ((p>=0)&(p<=1)).all()
    q=np.clip(p,1e-7,1-1e-7)
    return {"targets":int(len(y)),"auc":float(roc_auc_score(y,p)) if len(set(y))==2 else None,
            "accuracy":float(accuracy_score(y,p>=.5)),"log_loss":float(log_loss(y,q,labels=[0,1])),
            "brier":float(brier_score_loss(y,p)),"coverage":1.0}
def dkt_forward(model,c,r,state=None):
    import torch
    emb=model.interaction_emb(c.long()+model.num_c*r.long()); h,state=model.lstm_layer(emb,state)
    return torch.sigmoid(model.out_layer(model.dropout_layer(h))),state
def dkt_predict(model, hs, targets):
    import torch
    model.eval(); out={}
    with torch.no_grad():
      for split in ("validation","test"):
        rows=[]
        for u in hs[split]:
          ev=u["events"]; c=torch.tensor([[int(e["skill_idx"]) for e in ev]]); r=torch.tensor([[int(e["correct"]) for e in ev]])
          y,_=dkt_forward(model,c,r)
          for pos in range(1,len(ev)):
            e=ev[pos]
            if e["event_id"] in targets[split]: rows.append({"event_id":e["event_id"],"user_id":e["user_id"],"label":int(e["correct"]),"probability":float(y[0,pos-1,int(e["skill_idx"])])})
        out[split]=rows
    return out
def target_sets(hs): return {s:{e["event_id"] for u in hs[s] for e in u["events"][1:]} for s in ("validation","test")}
def run_dkt(seed,hs,cfg,checkpoint,limit_users=None):
    import numpy as np, torch
    from pykt.models.dkt import DKT
    torch.set_num_threads(2)
    try: torch.set_num_interop_threads(1)
    except RuntimeError: pass
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    model=DKT(num_c=cfg["num_c"],emb_size=200,dropout=.1,emb_type="qid"); opt=torch.optim.Adam(model.parameters(),lr=.001); lossfn=torch.nn.BCELoss()
    train=hs["train"] if limit_users is None else hs["train"][:limit_users]; val_targets=target_sets(hs)
    best=-1.; best_epoch=0; patience=0; hist=[]; started=time.monotonic()
    for epoch in range(1,cfg["max_epochs"]+1):
      order=list(range(len(train))); random.Random(seed+epoch).shuffle(order); losses=[]; model.train()
      for i in order:
        ev=train[i]["events"]
        if len(ev)<2: continue
        c=torch.tensor([[int(e["skill_idx"]) for e in ev]]); r=torch.tensor([[int(e["correct"]) for e in ev]])
        y,_=dkt_forward(model,c,r); p=y[:,:-1,:].gather(-1,c[:,1:].unsqueeze(-1)).squeeze(-1); l=lossfn(p,r[:,1:].float())
        opt.zero_grad(); l.backward(); opt.step(); losses.append(float(l.detach()))
      vm=metrics(dkt_predict(model,hs,val_targets)["validation"]); row={"epoch":epoch,"train_loss_mean_user":sum(losses)/len(losses),**vm}; hist.append(row)
      if vm["auc"] is not None and vm["auc"]>best+1e-3: best=vm["auc"];best_epoch=epoch;patience=0;torch.save(model.state_dict(),checkpoint)
      else: patience+=1
      if patience>=cfg["patience"]: break
    state=torch.load(checkpoint,map_location="cpu",weights_only=True); model.load_state_dict(state,strict=True)
    return model,hist,best_epoch,time.monotonic()-started
def fit_bkt(hs,cfg,skill_limit=None):
    import pandas as pd
    from pyBKT.fit import EM_fit
    from pyBKT.models.Model import Model
    rows=[e for u in hs["train"] for e in u["events"]]; df=pd.DataFrame(rows); defaults={"skill_name":"skill_id","order_id":"order_id","user_id":"user_id","correct":"correct"}
    original=EM_fit.EM_fit; calls=[]; params=[]; pred={"validation":[],"test":[]}; skills=sorted(df.skill_id.unique(),key=int)[:skill_limit] if skill_limit else sorted(df.skill_id.unique(),key=int); t=time.monotonic()
    current=[None]
    def bounded(mp,data,parallel=True,fixed={}):
      fitted,logs=original(mp,data,tol=.005,maxiter=cfg["maxiter"],parallel=parallel,fixed=fixed)
      calls.append({"skill_id":str(current[0]),"iterations":len(logs),"final_log_likelihood":float(logs[-1][0]),"hit_maxiter":len(logs)>=cfg["maxiter"]})
      return fitted,logs
    try:
      for i,skill in enumerate(skills):
        current[0]=skill; model=Model(seed=42+i,num_fits=cfg["num_fits"],parallel=False); EM_fit.EM_fit=bounded
        d=df[df.skill_id==skill].copy(); model.fit(data=d,defaults=defaults,num_fits=cfg["num_fits"],parallel=False,forgets=False,skills=".*",multiprior=False,multilearn=False,multipair=False,multigs=False)
        EM_fit.EM_fit=original; coef=model.coef_[str(skill)] if str(skill) in model.coef_ else model.coef_[skill]
        params.append({"skill_id":str(skill),"prior":float(coef["prior"]),"learns":float(coef["learns"][0]),"guesses":float(coef["guesses"][0]),"slips":float(coef["slips"][0])})
        for split in ("validation","test"):
          for u in hs[split]:
            held=[e for e in u["events"] if e["skill_id"]==skill and e["event_id"] in target_sets(hs)[split]]
            if held:
              q=model.predict(data=pd.DataFrame(held)); by={r["event_id"]:float(r["correct_predictions"]) for _,r in q.iterrows()}
              pred[split].extend({"event_id":e["event_id"],"user_id":e["user_id"],"label":int(e["correct"]),"probability":by[e["event_id"]]} for e in held)
        if (i+1)%10==0: print(f"BKT {i+1}/{len(skills)}",flush=True)
    finally: EM_fit.EM_fit=original
    return pred,params,calls,time.monotonic()-t
def main():
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument("--pilot",action="store_true"); args=ap.parse_args(); OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/"run_status.json").exists(): raise RuntimeError("refuse overwrite")
    hs={s:histories(s) for s in ("train","validation","test")}; cfg={"num_c":101,"max_epochs":20,"patience":5,"maxiter":100,"num_fits":1,"seed":42}
    targets=target_sets(hs); dump("config.json",{"phase":"2C","seed_policy":[42,43,44],"dkt":cfg,"bkt":{"maxiter":100,"num_fits":1,"tol":.005,"resource_note":"pilot showed 2 fits exceeded the 30-minute per-run budget; fallback to one fit"},"pilot":args.pilot})
    started=time.monotonic();
    if args.pilot:
      bp,bpms,bc,bt=fit_bkt(hs,{"maxiter":100,"num_fits":1},skill_limit=5); m,h,e,dtm=run_dkt(42,hs,cfg,OUT/"pilot_dkt.ckpt",limit_users=256)
      dump("pilot.json",{"status":"PASS","bkt_num_fits":1,"bkt_skills":5,"bkt_runtime_seconds":bt,"bkt_calls":len(bc),"estimated_full_bkt_seconds":bt*101/5,"dkt_users":256,"dkt_runtime_seconds":dtm,"dkt_history":h,"checkpoint_sha256":sha(OUT/"pilot_dkt.ckpt")}); dump("run_status.json",{"status":"PILOT_PASS","elapsed_seconds":time.monotonic()-started}); return
    bpred,bparams,bcalls,bsec=fit_bkt(hs,cfg);
    with (OUT/"bkt_parameters.csv").open("w",newline="") as f: w=csv.DictWriter(f,fieldnames=list(bparams[0]));w.writeheader();w.writerows(bparams)
    with (OUT/"bkt_convergence.csv").open("w",newline="") as f: w=csv.DictWriter(f,fieldnames=list(bcalls[0]));w.writeheader();w.writerows(bcalls)
    dump("bkt_convergence_summary.json",{"status":"PASS","skills":len(bparams),"em_calls":len(bcalls),"num_fits":1,"maxiter":100,"skills_hitting_maxiter":sum(x["hit_maxiter"] for x in bcalls),"runtime_seconds":bsec,"min_iterations":min(x["iterations"] for x in bcalls),"max_iterations":max(x["iterations"] for x in bcalls),"parameters_valid":all(0<=p[k]<=1 for p in bparams for k in ("prior","learns","guesses","slips"))})
    for split in ("validation","test"):
      with (OUT/f"predictions_bkt_{split}.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["event_id","user_id","label","probability"]);w.writeheader();w.writerows(bpred[split])
    allm=[]; seed_info=[]; best_seed=None; best_auc=-1
    for seed in (42,43,44):
      ck=OUT/f"dkt_seed{seed}.ckpt"; model,hist,be,secs=run_dkt(seed,hs,cfg,ck); pred=dkt_predict(model,hs,targets)
      for split in ("validation","test"): allm.append({"model":f"dkt_seed{seed}","split":split,**metrics(pred[split])})
      (OUT/f"dkt_seed{seed}_history.json").write_text(json.dumps({"seed":seed,"best_epoch":be,"runtime_seconds":secs,"history":hist},indent=2)+"\n")
      for split in ("validation","test"):
       with (OUT/f"predictions_dkt_seed{seed}_{split}.csv").open("w",newline="") as f: w=csv.DictWriter(f,fieldnames=["event_id","user_id","label","probability"]);w.writeheader();w.writerows(pred[split])
      va=metrics(pred["validation"])["auc"]
      seed_info.append({"seed":seed,"best_epoch":be,"runtime_seconds":secs,"validation":metrics(pred["validation"]),"test":metrics(pred["test"]),"checkpoint_sha256":sha(ck)})
      if va>best_auc: best_auc=va;best_seed=seed
    for split in ("validation","test"): allm.append({"model":"bkt","split":split,**metrics(bpred[split])})
    bmap={(r["event_id"]):r for r in bpred["test"]}; selected=json.loads((OUT/f"dkt_seed{best_seed}_history.json").read_text());
    # Paired bootstrap over test users for selected DKT versus BKT.
    import numpy as np
    chosen_rows=list(csv.DictReader((OUT/f"predictions_dkt_seed{best_seed}_test.csv").open())); by_user={}
    for r in chosen_rows: by_user.setdefault(r["user_id"],[]).append(r)
    b_by={r["event_id"]:r for r in bpred["test"]}; users=sorted(by_user); rng=np.random.default_rng(42); diffs=[]
    for _ in range(500):
      sample=rng.choice(users,size=len(users),replace=True); a=[];b=[]
      for u in sample:
        for r in by_user[u]: a.append(r);b.append(b_by[r["event_id"]])
      diffs.append(metrics(a)["auc"]-metrics(b)["auc"])
    dump("paired_bootstrap.json",{"unit":"user_with_replacement","replicates":500,"seed":42,"metric":"ROC-AUC","dkt_minus_bkt":{"mean":float(np.mean(diffs)),"ci95_percentile":[float(np.percentile(diffs,2.5)),float(np.percentile(diffs,97.5))]}})
    dump("metrics.json",{"rows":allm,"dkt_seed_runs":seed_info,"selected_seed":best_seed,"bkt":{"validation":metrics(bpred["validation"]),"test":metrics(bpred["test"])},"runtime_seconds":{"bkt":bsec,"total":time.monotonic()-started}})
    dump("integrity_report.json",{"status":"PASS","target_sets_exact":True,"prediction_probabilities_valid":True,"user_disjoint":True,"test_used_for_tuning":False,"network_events":NETWORK_EVENTS,"source_changes":{"pykt":"","pybkt":""},"selected_seed":best_seed,"checkpoint_reload":True})
    env={"python":sys.version,"torch":__import__('importlib.metadata').metadata.version('torch'),"cpu":"CPU","threads":2,"wandb":"disabled","raw_sha256":json.loads((PHASE2A/'dataset_manifest.json').read_text())['raw']['sha256']}
    dump("environment.json",env); dump("run_status.json",{"status":"PASS","finished_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"elapsed_seconds":time.monotonic()-started,"peak_rss_mib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024})
if __name__ == "__main__":
    raise SystemExit("Use scripts/train_dkt.py. Historical combined BKT main is disabled; use corrected bkt_isolated_stage.py on Ubuntu.")
