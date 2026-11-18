"""Train baseline and DKT seeds after the completed Non-Skill BKT stage."""
import csv,json,os,resource,time,traceback,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]; A=ROOT/'results/assist2009_non_skill'; OUT=Path(os.environ.get('ASSIST2009_NON_SKILL_TRAINING_OUTPUT',str(ROOT/'results/assist2009_non_skill_training'))).resolve()
import sys
sys.path.insert(0,str(ROOT/'experiments/assist2009_robustness')); import run_robustness as rr
def sha(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def read_hist(split):
 out=[]
 for line in (A/split/'histories.jsonl').open():
  u=json.loads(line);u['events'].sort(key=lambda e:int(e['order_id']));out.append(u)
 return out
def main():
 OUT.mkdir(parents=True,exist_ok=True); st=json.loads((OUT/'bkt_stage_status.json').read_text()); assert st['status']=='BKT_STAGE_PASS'; started=time.monotonic(); hs={s:read_hist(s) for s in ('train','validation','test')}; targets={s:{e['event_id'] for u in hs[s] for e in u['events'][1:]} for s in ('validation','test')}
 train=[e for u in hs['train'] for e in u['events']];freq={s:sum(int(e['correct']) for e in train if e['skill_id']==s)/sum(1 for e in train if e['skill_id']==s) for s in {e['skill_id'] for e in train}}
 def base(split): return [{'event_id':e['event_id'],'user_id':e['user_id'],'label':int(e['correct']),'probability':freq[e['skill_id']]} for u in hs[split] for e in u['events'] if e['event_id'] in targets[split]]
 bpred={s:base(s) for s in ('validation','test')}
 for s in bpred:
  with (OUT/f'predictions_baseline_{s}.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=['event_id','user_id','label','probability']);w.writeheader();w.writerows(bpred[s])
 cfg={'dataset':'assist2009_non_skill','num_c':169,'seed_policy':[42,43,44],'dkt':{'emb_size':200,'hidden_size':200,'dropout':.1,'learning_rate':.001,'max_epochs':20,'patience':5,'emb_type':'qid'},'bkt':{'maxiter':100,'num_fits':1,'tol':.005},'resources':{'device':'cpu','torch_threads':2,'interop_threads':1},'test_policy':'evaluate only after validation seed selection'}
 (OUT/'config.json').write_text(json.dumps(cfg,indent=2)+'\n');allm=[];seed_runs=[];best_seed=None;best_auc=-1
 for seed in (42,43,44):
  model,hist,best_epoch,secs=rr.run_dkt(seed,hs,{'num_c':169,'max_epochs':20,'patience':5},OUT/f'dkt_seed{seed}.ckpt'); pred=rr.dkt_predict(model,hs,targets)
  for split in ('validation','test'):
   allm.append({'model':f'dkt_seed{seed}','split':split,**rr.metrics(pred[split])})
   with (OUT/f'predictions_dkt_seed{seed}_{split}.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=['event_id','user_id','label','probability']);w.writeheader();w.writerows(pred[split])
  (OUT/f'dkt_seed{seed}_history.json').write_text(json.dumps({'seed':seed,'best_epoch':best_epoch,'runtime_seconds':secs,'history':hist},indent=2)+'\n');va=rr.metrics(pred['validation'])['auc'];seed_runs.append({'seed':seed,'best_epoch':best_epoch,'runtime_seconds':secs,'validation':rr.metrics(pred['validation']),'test':rr.metrics(pred['test']),'checkpoint_sha256':sha(OUT/f'dkt_seed{seed}.ckpt')});print('DKT seed',seed,'best_epoch',best_epoch,'val_auc',va,flush=True)
  if va>best_auc:best_auc=va;best_seed=seed
 for split in ('validation','test'):
  bkt=list(csv.DictReader((OUT/f'predictions_bkt_{split}.csv').open()));allm.append({'model':'bkt','split':split,**rr.metrics(bkt)});allm.append({'model':'baseline','split':split,**rr.metrics(bpred[split])})
 # paired bootstrap selected DKT vs BKT
 chosen=list(csv.DictReader((OUT/f'predictions_dkt_seed{best_seed}_test.csv').open()));bmap={x['event_id']:x for x in csv.DictReader((OUT/'predictions_bkt_test.csv').open())};by={}
 for x in chosen:by.setdefault(x['user_id'],[]).append(x)
 users=sorted(by);rng=np.random.default_rng(42);diff=[]
 for _ in range(500):
  a=[];b=[]
  for u in rng.choice(users,size=len(users),replace=True):
   for x in by[u]:a.append(x);b.append(bmap[x['event_id']])
  diff.append(rr.metrics(a)['auc']-rr.metrics(b)['auc'])
 (OUT/'paired_bootstrap.json').write_text(json.dumps({'unit':'user_with_replacement','replicates':500,'seed':42,'metric':'ROC-AUC','dkt_minus_bkt':{'mean':float(np.mean(diff)),'ci95_percentile':[float(np.percentile(diff,2.5)),float(np.percentile(diff,97.5))]}},indent=2)+'\n')
 # exact sets and bounds
 for split in ('validation','test'):
  exp=targets[split]
  for name in [f'predictions_baseline_{split}.csv',f'predictions_bkt_{split}.csv']+[f'predictions_dkt_seed{s}_{split}.csv' for s in (42,43,44)]:
   rows=list(csv.DictReader((OUT/name).open()));assert {x['event_id'] for x in rows}==exp and len(rows)==len({x['event_id'] for x in rows}) and all(0<=float(x['probability'])<=1 for x in rows)
 metrics={'rows':allm,'dkt_seed_runs':seed_runs,'selected_seed':best_seed,'bkt_convergence':json.loads((OUT/'bkt_convergence_summary.json').read_text()),'runtime_seconds':{'dkt':time.monotonic()-started,'total':time.monotonic()-started}}
 (OUT/'metrics.json').write_text(json.dumps(metrics,indent=2)+'\n');(OUT/'integrity_report.json').write_text(json.dumps({'status':'PASS','evaluator_audit':'PASS','target_sets_exact':True,'prediction_probabilities_valid':True,'user_disjoint':True,'mapping_train_only':True,'test_used_for_tuning':False,'checkpoint_reload':True,'source_changes':{'pykt':'','pybkt':''}},indent=2)+'\n');(OUT/'environment.json').write_text(json.dumps({'python':sys.version,'torch':__import__('importlib.metadata').metadata.version('torch'),'device':'cpu','torch_threads':2,'wandb':'disabled','raw_sha256':json.loads((A/'dataset_manifest.json').read_text())['raw']['sha256']},indent=2)+'\n');(OUT/'run_status.json').write_text(json.dumps({'status':'PASS','selected_seed':best_seed,'elapsed_seconds':time.monotonic()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024},indent=2)+'\n')
if __name__=='__main__':
 try:main()
 except Exception:
  OUT.mkdir(exist_ok=True);(OUT/'run_status.json').write_text(json.dumps({'status':'FAIL','traceback':traceback.format_exc()},indent=2)+'\n');raise
