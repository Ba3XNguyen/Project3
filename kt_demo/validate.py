"""Run checkpoint inference and independent artifact checks; write only kt_demo/."""
import hashlib
import json
import platform
import random
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from core import CONFIG, ROOT, paths, histories, read_json, load_data, metrics, load_model, predict_history, prediction_paths, pseudonym

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def validate(name):
    data, run, seed, n = paths(name)
    watched = [p for folder in (data,run,ROOT/'results/assist2009_phase2b_run3') for p in folder.rglob('*') if p.is_file()]
    watched += [ROOT/'code/pykt-toolkit/pykt/models/dkt.py']
    original_hashes = {p:sha(p) for p in watched}
    events, predictions = load_data(name)
    hs = {s:histories(data,s) for s in ('train','validation','test')}
    users = {s:{str(u['uid']) for u in rows} for s,rows in hs.items()}
    assert all(not users[a]&users[b] for a,b in [('train','test'),('train','validation'),('test','validation')])
    manifest_users = read_json(data/'split_manifest.json')['users']
    assert all(users[s] == set(map(str,manifest_users[s])) for s in users)
    shuffled = sorted(int(u) for group in users.values() for u in group)
    random.Random(42).shuffle(shuffled)
    ntrain,nvalid = int(.7*len(shuffled)),int(.15*len(shuffled))
    recreated = {'train':shuffled[:ntrain],'validation':shuffled[ntrain:ntrain+nvalid],'test':shuffled[ntrain+nvalid:]}
    assert all(users[s] == set(map(str,recreated[s])) for s in users)
    mapping_artifact = read_json(data/'skill_mapping.json')
    mapping = {str(v):str(k) for k,v in mapping_artifact['skill_to_idx'].items()}
    train_skills = {str(e['skill_id']) for u in hs['train'] for e in u['events']}
    assert set(mapping.values()) == train_skills and len(mapping) == n
    train_events = pd.DataFrame([e for u in hs['train'] for e in u['events']])
    freq = train_events.groupby('skill_id').correct.mean()
    baseline_delta = float(np.max(np.abs(events.loc[events.position>0,'skill_id'].map(freq).to_numpy()-predictions['Baseline'].probability.to_numpy())))
    assert baseline_delta < 1e-12
    for split, rows in hs.items():
        for u in rows:
            ev = u['events']
            assert len({int(e['order_id']) for e in ev}) == len(ev)
            assert all(str(e['user_id']) == str(u['uid']) and e['split'] == split for e in ev)
            assert all(mapping[str(e['skill_idx'])] == str(e['skill_id']) for e in ev)
    # Independently compare histories to the event table and eligibility artifact.
    raw = pd.read_csv(data/'events.csv').set_index('event_id')
    aligned = raw.loc[events.event_id]
    for col in ('skill_id','skill_idx','correct','user_id','order_id'):
        assert np.array_equal(aligned[col].astype(str).to_numpy(),events[col].astype(str).to_numpy()), col
    eligible = pd.read_csv(data/'target_eligibility.csv')
    target_col = next((c for c in ('common_target','eligible','is_target') if c in eligible),None)
    if target_col:
        subset = eligible[(eligible.split == 'test') & (eligible[target_col] == 1)]
        assert set(subset.event_id) == set(predictions['DKT'].index)
    checkpoint = run/f'dkt_seed{seed}.ckpt'
    before = sha(checkpoint)
    manifest = pd.read_csv(ROOT/'presentation/ARTIFACT_MANIFEST.csv')
    manifest_checked = 0
    for path in [checkpoint,data/'skill_mapping.json',data/'test/histories.jsonl',*prediction_paths(name).values()]:
        record = manifest[manifest.path == path.relative_to(ROOT).as_posix()]
        assert len(record) == 1, str(path)
        assert record.iloc[0].sha256 == sha(path), str(path)
        manifest_checked += 1
    model, structure = load_model(name)
    diffs = []
    for u in hs['test']:
        ev = u['events']
        if len(ev)<2: continue
        p = predict_history(model,ev)
        saved = predictions['DKT'].loc[[e['event_id'] for e in ev[1:]],'probability'].to_numpy()
        diffs.extend(np.abs(p-saved).tolist())
    # Real-data causal check: flip target and future responses; prior output must be unchanged.
    causal = []
    for u in [u for u in hs['test'] if len(u['events']) >= 4][:10]:
        ev = u['events']; pos = len(ev)//2
        original = predict_history(model,ev)[pos-1]
        mutated = [dict(e,correct=1-int(e['correct'])) if i>=pos else dict(e) for i,e in enumerate(ev)]
        altered = predict_history(model,mutated)[pos-1]
        prefix = predict_history(model,ev[:pos+1])[pos-1]
        causal.append(max(abs(original-altered),abs(original-prefix)))
    assert max(causal) <= 1e-6
    assert before == sha(checkpoint)
    recalculated = {}
    for label, df in predictions.items():
        path = prediction_paths(name)[label]
        saved_metrics = read_json(path.parent/'metrics.json')
        stored = saved_metrics.get('rows',list(saved_metrics.get('metrics',{}).values()))
        key = f'dkt_seed{seed}' if label == 'DKT' else label.lower()
        expected = next(x for x in stored if x['model'] == key and x['split'] == 'test')
        value = metrics(df)
        delta = {k:abs(v-expected[k]) for k,v in value.items()}
        assert max(delta.values()) < 1e-10
        recalculated[label] = dict(value, metric_max_delta=max(delta.values()), targets=len(df))
    seeds = read_json(run/'metrics.json')
    assert seeds['selected_seed'] == seed
    assert seed == max(seeds['dkt_seed_runs'],key=lambda x:x['validation']['auc'])['seed']
    differences = np.array(diffs)
    assert differences.max() <= 1e-6
    assert all(sha(p) == h for p,h in original_hashes.items())
    return dict(status='PASS', seed=seed, checkpoint=str(checkpoint.relative_to(ROOT)), checkpoint_sha256=before,
                checkpoint_structure=structure, inference_targets=len(diffs), tolerance=1e-6,
                max_probability_difference=float(differences.max()), match_fraction=float(np.mean(differences<=1e-6)),
                causal_max_difference=max(causal), causal_real_histories=len(causal), metrics=recalculated,
                learners={s:len(v) for s,v in users.items()}, learner_disjoint=True, mapping_train_only=True,
                event_table_alignment=True, eligibility_checked=bool(target_col), presentation_manifest_files_verified=manifest_checked,
                original_files_hash_unchanged=len(original_hashes), baseline_train_frequency_max_difference=baseline_delta,
                examples=events.groupby('learner').size().sort_values(ascending=False).head(5).to_dict(),
                input_sha256={str(p.relative_to(ROOT)):sha(p) for p in [checkpoint,data/'skill_mapping.json',data/'test/histories.jsonl',*prediction_paths(name).values()]})

if __name__ == '__main__':
    torch.set_num_threads(2)
    result = {'platform':platform.platform(),'python':sys.version,'torch':torch.__version__,'datasets':{}}
    for name in CONFIG:
        try:
            result['datasets'][name] = validate(name)
            print(name,json.dumps(result['datasets'][name],ensure_ascii=False),flush=True)
        except Exception as exc:
            import traceback
            result['datasets'][name] = {'status':'FAIL','error':str(exc),'traceback':traceback.format_exc()}
            print(result['datasets'][name]['traceback'],flush=True)
    (ROOT/'kt_demo/validation_results.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    if any(x['status']!='PASS' for x in result['datasets'].values()): sys.exit(1)
