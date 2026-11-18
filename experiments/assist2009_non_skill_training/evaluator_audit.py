"""Independent pyBKT one-step audit on a tiny, hand-checkable protocol."""
import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[2]
def main():
    import sys
    sys.path.insert(0,str(ROOT/'code/pyBKT/source-py'))
    from pyBKT.models.Model import Model
    rows=[{'user_id':1,'order_id':i,'skill_id':'s','correct':int(i%2)} for i in range(1,20)]+[{'user_id':2,'order_id':i,'skill_id':'s','correct':int(i%2)} for i in range(1,20)]
    df=pd.DataFrame(rows); m=Model(seed=1,num_fits=1,parallel=False)
    m.fit(data=df,defaults={'skill_name':'skill_id','order_id':'order_id','user_id':'user_id','correct':'correct'},num_fits=1,parallel=False,skills='.*',forgets=False,multiprior=False,multilearn=False,multipair=False,multigs=False)
    full=m.predict(data=df).sort_values(['user_id','order_id']).reset_index(drop=True)
    p=float(m.coef_['s']['prior']); learn=float(m.coef_['s']['learns'][0]); guess=float(m.coef_['s']['guesses'][0]); slip=float(m.coef_['s']['slips'][0])
    def emission(q): return guess*(1-q)+(1-slip)*q
    def update(q,y):
        post=((1-slip)*q/emission(q)) if y else (slip*q/(1-emission(q)))
        return post+(1-post)*learn
    manual0=emission(p); manual1=emission(update(p,1))
    # Full output at t=2 must equal prefix output with only events through t=2.
    prefix=m.predict(data=df[(df.user_id==1)&(df.order_id<=2)]).sort_values('order_id')
    target_full=float(full[(full.user_id==1)&(full.order_id==2)].iloc[0].correct_predictions)
    target_prefix=float(prefix[prefix.order_id==2].iloc[0].correct_predictions)
    target_only=float(m.predict(data=df[(df.user_id==1)&(df.order_id==2)]).iloc[0].correct_predictions)
    user2_first=float(full[(full.user_id==2)&(full.order_id==1)].iloc[0].correct_predictions)
    assert abs(float(full.iloc[0].correct_predictions)-manual0)<1e-6
    assert abs(target_full-manual1)<1e-6 and abs(target_full-target_prefix)<1e-9
    assert abs(target_full-target_only)>1e-5
    # Changing target/future labels must not change prediction at order 2.
    altered=df.copy(); altered.loc[(altered.user_id==1)&(altered.order_id>=2),'correct']=1-altered.loc[(altered.user_id==1)&(altered.order_id>=2),'correct']
    altered_pred=m.predict(data=altered); altered_t=float(altered_pred[(altered_pred.user_id==1)&(altered_pred.order_id==2)].iloc[0].correct_predictions)
    assert abs(altered_t-target_full)<1e-9
    out={'status':'PASS','manual_initial_prediction':manual0,'manual_after_first_response_prediction':manual1,'pybkt_full_target_prediction':target_full,'pybkt_prefix_target_prediction':target_prefix,'target_only_control_prediction':target_only,'context_changes_prediction':True,'future_label_invariance':True,'user_state_reset':abs(user2_first-float(full.iloc[0].correct_predictions))<1e-9,'parameters':{'prior':p,'learn':learn,'guess':guess,'slip':slip}}
    outdir=ROOT/'results/assist2009_non_skill_training'; outdir.mkdir(parents=True,exist_ok=True); (outdir/'bkt_evaluator_audit.json').write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))
if __name__=='__main__': main()
