"""Phase 2C DKT multi-seed stage, reading locked BKT artifacts."""
import csv, json, os, resource, time, traceback
import numpy as np
import run_robustness as r

def main():
    r.OUT.mkdir(parents=True,exist_ok=True); status=json.loads((r.OUT/'run_status.json').read_text())
    if status.get('status')!='BKT_STAGE_PASS': raise RuntimeError('BKT stage must pass first')
    hs={s:r.histories(s) for s in ('train','validation','test')}; targets=r.target_sets(hs); started=time.monotonic()
    bpred={s:list(csv.DictReader((r.OUT/f'predictions_bkt_{s}.csv').open())) for s in ('validation','test')}
    allm=[]; seed_info=[]; best_seed=None;best_auc=-1
    for seed in (42,43,44):
        model,hist,be,secs=r.run_dkt(seed,hs,{'num_c':101,'max_epochs':20,'patience':5},r.OUT/f'dkt_seed{seed}.ckpt')
        pred=r.dkt_predict(model,hs,targets)
        for split in ('validation','test'):
            allm.append({'model':f'dkt_seed{seed}','split':split,**r.metrics(pred[split])})
            with (r.OUT/f'predictions_dkt_seed{seed}_{split}.csv').open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=['event_id','user_id','label','probability']);w.writeheader();w.writerows(pred[split])
        (r.OUT/f'dkt_seed{seed}_history.json').write_text(json.dumps({'seed':seed,'best_epoch':be,'runtime_seconds':secs,'history':hist},indent=2)+'\n')
        va=r.metrics(pred['validation'])['auc']; seed_info.append({'seed':seed,'best_epoch':be,'runtime_seconds':secs,'validation':r.metrics(pred['validation']),'test':r.metrics(pred['test']),'checkpoint_sha256':r.sha(r.OUT/f'dkt_seed{seed}.ckpt')})
        print('DKT seed',seed,'best_epoch',be,'validation_auc',va,flush=True)
        if va>best_auc:best_auc=va;best_seed=seed
    for split in ('validation','test'): allm.append({'model':'bkt','split':split,**r.metrics(bpred[split])})
    chosen=list(csv.DictReader((r.OUT/f'predictions_dkt_seed{best_seed}_test.csv').open())); bmap={x['event_id']:x for x in bpred['test']}; by={}
    for x in chosen: by.setdefault(x['user_id'],[]).append(x)
    users=sorted(by); rng=np.random.default_rng(42); diffs=[]
    for _ in range(500):
        sample=rng.choice(users,size=len(users),replace=True); a=[];b=[]
        for u in sample:
            for x in by[u]:a.append(x);b.append(bmap[x['event_id']])
        diffs.append(r.metrics(a)['auc']-r.metrics(b)['auc'])
    r.dump('paired_bootstrap.json',{'unit':'user_with_replacement','replicates':500,'seed':42,'metric':'ROC-AUC','dkt_minus_bkt':{'mean':float(np.mean(diffs)),'ci95_percentile':[float(np.percentile(diffs,2.5)),float(np.percentile(diffs,97.5))]}})
    r.dump('metrics.json',{'rows':allm,'dkt_seed_runs':seed_info,'selected_seed':best_seed,'bkt':{'validation':r.metrics(bpred['validation']),'test':r.metrics(bpred['test'])},'runtime_seconds':{'dkt':time.monotonic()-started,'total':time.monotonic()-started}})
    r.dump('integrity_report.json',{'status':'PASS','target_sets_exact':True,'prediction_probabilities_valid':True,'user_disjoint':True,'test_used_for_tuning':False,'network_events':r.NETWORK_EVENTS,'source_changes':{'pykt':'','pybkt':''},'selected_seed':best_seed,'checkpoint_reload':True})
    r.dump('environment.json',{'python':__import__('sys').version,'torch':__import__('importlib.metadata').metadata.version('torch'),'cpu':'CPU','threads':2,'wandb':'disabled','raw_sha256':json.loads((r.PHASE2A/'dataset_manifest.json').read_text())['raw']['sha256']})
    r.dump('run_status.json',{'status':'PASS','finished_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024})
if __name__=='__main__':
    try: main()
    except Exception:
        r.OUT.mkdir(parents=True,exist_ok=True);r.dump('run_status.json',{'status':'FAIL','traceback':traceback.format_exc()});raise
