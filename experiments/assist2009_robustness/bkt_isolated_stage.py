import sys
"""Phase 2C BKT maxiter=100, one fresh process per skill."""
import csv,json,os,resource,subprocess,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; OUT=Path(os.environ.get('ASSIST2009_PHASE2C_OUTPUT',str(ROOT/'results/assist2009_phase2c'))).resolve()
def dump(n,x): (OUT/n).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def main():
    OUT.mkdir(parents=True,exist_ok=True); started=time.monotonic(); A=ROOT/'results/assist2009_phase2a'
    skills=sorted(json.loads((A/'skill_mapping.json').read_text())['skill_to_idx'],key=int); tmp=OUT/'bkt_one'; tmp.mkdir(exist_ok=True); results=[]
    for i,s in enumerate(skills,1):
        p=tmp/f'{s}.json'; env=dict(os.environ); env['PYTHONPATH']=str(ROOT/'experiments/assist2009_robustness')+os.pathsep+str(ROOT/'code/pyBKT/source-py')
        subprocess.run([sys.executable,'-B',str(ROOT/'experiments/assist2009_robustness/bkt_one.py'),s,str(p)],check=True,env=env)
        results.append(json.loads(p.read_text())); print(f'BKT isolated {i}/{len(skills)}',flush=True)
    params=[{'skill_id':x['skill_id'],**x['parameters']} for x in results]; calls=[{'skill_id':x['skill_id'],**x['convergence']} for x in results]; pred={s:sum((x['predictions'].get(s,[]) for x in results),[]) for s in ('validation','test')}
    with (OUT/'bkt_parameters.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(params[0])); w.writeheader(); w.writerows(params)
    with (OUT/'bkt_convergence.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(calls[0])); w.writeheader(); w.writerows(calls)
    for s in ('validation','test'):
        with (OUT/f'predictions_bkt_{s}.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['event_id','user_id','label','probability']); w.writeheader(); w.writerows(pred[s])
    dump('bkt_convergence_summary.json',{'status':'PASS','skills':len(results),'em_calls':len(calls),'num_fits':1,'maxiter':100,'tol':.005,'skills_hitting_maxiter':sum(x['hit_maxiter'] for x in calls),'runtime_seconds':time.monotonic()-started,'min_iterations':min(x['iterations'] for x in calls),'max_iterations':max(x['iterations'] for x in calls),'parameters_valid':all(0<=p[k]<=1 for p in params for k in ('prior','learns','guesses','slips'))})
    dump('bkt_metrics.json',{'targets':{s:len(pred[s]) for s in pred},'status':'PASS'}); dump('run_status.json',{'status':'BKT_STAGE_PASS','elapsed_seconds':time.monotonic()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024})
if __name__=='__main__':
    try: main()
    except Exception:
        OUT.mkdir(exist_ok=True); dump('run_status.json',{'status':'FAIL','traceback':traceback.format_exc()}); raise
