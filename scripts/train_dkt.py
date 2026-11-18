"""Thin CLI over the existing DKT training loop. Outputs must be NEW."""
import argparse
import csv
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True,help='Prepared folder with train/validation/test histories.jsonl and skill_mapping.json')
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--seed',type=int,default=42)
    ap.add_argument('--max-epochs',type=int,default=20)
    ap.add_argument('--patience',type=int,default=5)
    args=ap.parse_args()
    required=[args.data/'skill_mapping.json']+[args.data/s/'histories.jsonl' for s in ('train','validation','test')]
    if any(not p.is_file() for p in required): ap.error('Missing prepared data. See docs/ARTIFACT_SETUP.md and run preprocessing.')
    if args.output.exists(): ap.error('Output already exists. Choose a NEW run folder; refusing overwrite.')
    if args.max_epochs<1 or args.patience<1: ap.error('Epochs/patience must be positive')
    sys.path.insert(0,str(ROOT/'experiments/assist2009_robustness'))
    import run_robustness as rr
    hs={s:[] for s in ('train','validation','test')}
    for split in hs:
        with (args.data/split/'histories.jsonl').open(encoding='utf-8') as f: hs[split]=[json.loads(line) for line in f]
        for u in hs[split]: u['events'].sort(key=lambda e:int(e['order_id']))
    groups=[{str(u['uid']) for u in hs[s]} for s in hs]
    if any(groups[i]&groups[j] for i in range(3) for j in range(i)): ap.error('Learner split overlap')
    mapping=json.loads(required[0].read_text(encoding='utf-8'))
    n=mapping['num_c']; targets=rr.target_sets(hs)
    args.output.mkdir(parents=True)
    ck=args.output/f'dkt_seed{args.seed}.ckpt'
    model,hist,epoch,seconds=rr.run_dkt(args.seed,hs,{'num_c':n,'max_epochs':args.max_epochs,'patience':args.patience},ck)
    pred=rr.dkt_predict(model,hs,targets)
    rows=[]
    for split in pred:
        with (args.output/f'predictions_dkt_seed{args.seed}_{split}.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=['event_id','user_id','label','probability']);w.writeheader();w.writerows(pred[split])
        rows.append(dict(model=f'dkt_seed{args.seed}',split=split,**rr.metrics(pred[split])))
    (args.output/f'dkt_seed{args.seed}_history.json').write_text(json.dumps(dict(seed=args.seed,best_epoch=epoch,runtime_seconds=seconds,history=hist),indent=2),encoding='utf-8')
    (args.output/'metrics.json').write_text(json.dumps({'rows':rows,'seed':args.seed,'note':'Single-seed run; not the historical three-seed benchmark.'},indent=2),encoding='utf-8')
    print('PASS: DKT training, safe checkpoint reload and evaluation completed in '+str(args.output))

if __name__=='__main__': main()
