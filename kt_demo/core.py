"""Read-only access to original experiment artifacts. No training code."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, accuracy_score, log_loss, brier_score_loss

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {
    'Skill Builder': ('assist2009_phase2a', 'assist2009_phase2c', 42, 101),
    'Non-Skill Builder': ('assist2009_non_skill', 'assist2009_non_skill_training', 43, 169),
}

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def paths(name):
    data, run, seed, n = CONFIG[name]
    return ROOT/'results'/data, ROOT/'results'/run, seed, n

def histories(data, split):
    with (data/split/'histories.jsonl').open(encoding='utf-8') as f:
        result = [json.loads(line) for line in f]
    for u in result:
        u['events'].sort(key=lambda e: int(e['order_id']))
    return result

def pseudonym(name, uid):
    # Dataset-scoped display alias; never reads the private integration key.
    return 'Learner-' + hashlib.sha256(f'kt-demo-v1:{name}:{uid}'.encode()).hexdigest()[:16]

def prediction_paths(name):
    _, run, seed, _ = paths(name)
    baseline = ROOT/'results/assist2009_phase2b_run3' if name == 'Skill Builder' else run
    return {'Baseline': baseline/'predictions_baseline_test.csv',
            'BKT': run/'predictions_bkt_test.csv',
            'DKT': run/f'predictions_dkt_seed{seed}_test.csv'}

def metrics(df):
    y, p = df.label.to_numpy(), df.probability.to_numpy()
    assert np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all()
    return dict(auc=float(roc_auc_score(y,p)), accuracy=float(accuracy_score(y,p >= .5)),
                log_loss=float(log_loss(y,np.clip(p,1e-7,1-1e-7),labels=[0,1])),
                brier=float(brier_score_loss(y,p)))

def load_data(name):
    data, _, _, _ = paths(name)
    hs = histories(data,'test')
    events = pd.DataFrame([dict(e, position=i, learner=pseudonym(name,u['uid']))
                           for u in hs for i,e in enumerate(u['events'])])
    assert events.event_id.is_unique
    targets = events[events.position > 0].set_index('event_id')
    predictions = {}
    for model, path in prediction_paths(name).items():
        df = pd.read_csv(path, dtype={'event_id':str, 'user_id':str}).set_index('event_id')
        assert df.index.is_unique and set(df.index) == set(targets.index), f'{model}: target IDs differ'
        df = df.loc[targets.index]
        assert np.array_equal(df.label, targets.correct.astype(int))
        assert np.array_equal(df.user_id, targets.user_id.astype(str))
        metrics(df)
        predictions[model] = df
    for model, df in predictions.items():
        events[model] = events.event_id.map(df.probability)
    assert events.groupby('user_id').learner.first().is_unique
    return events, predictions

def load_model(name):
    import torch
    _, run, seed, n = paths(name)
    spec = importlib.util.spec_from_file_location('demo_original_dkt', ROOT/'code/pykt-toolkit/pykt/models/dkt.py')
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    checkpoint = run/f'dkt_seed{seed}.ckpt'
    state = torch.load(checkpoint, map_location='cpu', weights_only=True)
    assert isinstance(state, dict) and all(isinstance(v,torch.Tensor) for v in state.values())
    model = module.DKT(num_c=n,emb_size=200,dropout=.1,emb_type='qid')
    model.load_state_dict(state,strict=True)
    model.eval()
    return model, {k:list(v.shape) for k,v in state.items()}

def predict_history(model, events):
    import torch
    c = torch.tensor([[int(e['skill_idx']) for e in events]])
    r = torch.tensor([[int(e['correct']) for e in events]])
    with torch.inference_mode():
        out = model(c,r)
    return np.array([float(out[0,i-1,int(events[i]['skill_idx'])]) for i in range(1,len(events))])
