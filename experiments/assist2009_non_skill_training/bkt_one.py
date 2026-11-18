"""Fit one Non-Skill-Builder BKT skill in a fresh process."""
import csv,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; A=ROOT/'results/assist2009_non_skill'; skill=sys.argv[1]; out=Path(sys.argv[2]); sys.path.insert(0,str(ROOT/'code/pyBKT/source-py'))
import pandas as pd
from pyBKT.fit import EM_fit
from pyBKT.models.Model import Model
hs={}
for s in ('train','validation','test'):
    hs[s]=[]
    for line in (A/s/'histories.jsonl').open():
        u=json.loads(line);u['events'].sort(key=lambda e:int(e['order_id']));hs[s].append(u)
target={s:{x['event_id'] for x in csv.DictReader((A/'target_eligibility.csv').open()) if x['split']==s and x['common_target']=='1'} for s in ('validation','test')}
rows=[e for u in hs['train'] for e in u['events'] if str(e['skill_id'])==skill]; df=pd.DataFrame(rows); calls=[]; original=EM_fit.EM_fit
def bounded(mp,data,parallel=True,fixed={}):
    fitted,logs=original(mp,data,tol=.005,maxiter=100,parallel=parallel,fixed=fixed);calls.append({'iterations':len(logs),'final_log_likelihood':float(logs[-1][0]),'hit_maxiter':len(logs)>=100});return fitted,logs
EM_fit.EM_fit=bounded;started=time.monotonic();m=Model(seed=42+int(skill),num_fits=1,parallel=False)
try:m.fit(data=df,defaults={'skill_name':'skill_id','order_id':'order_id','user_id':'user_id','correct':'correct'},num_fits=1,parallel=False,forgets=False,skills='.*',multiprior=False,multilearn=False,multipair=False,multigs=False)
finally:EM_fit.EM_fit=original
coef=m.coef_.get(str(skill),m.coef_.get(skill));res={'skill_id':skill,'parameters':{'prior':float(coef['prior']),'learns':float(coef['learns'][0]),'guesses':float(coef['guesses'][0]),'slips':float(coef['slips'][0])},'convergence':calls[0],'runtime_seconds':time.monotonic()-started,'predictions':{}}
for split in ('validation','test'):
    selected=[]
    for u in hs[split]:
        seq=[e for e in u['events'] if str(e['skill_id'])==skill]
        if not seq:continue
        q=m.predict(data=pd.DataFrame(seq));by={r['event_id']:float(r['correct_predictions']) for _,r in q.iterrows()}
        selected.extend({'event_id':e['event_id'],'user_id':e['user_id'],'label':int(e['correct']),'probability':by[e['event_id']]} for e in seq if e['event_id'] in target[split])
    res['predictions'][split]=selected
out.write_text(json.dumps(res,allow_nan=False));print(json.dumps({'skill':skill,'seconds':res['runtime_seconds']}),flush=True)
