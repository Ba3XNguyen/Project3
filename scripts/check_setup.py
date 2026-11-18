"""Check local dependencies and explicitly report missing private artifacts."""
import importlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/pykt-toolkit'),str(ROOT/'code/pyBKT/source-py'),str(ROOT/'kt_demo')]
for module in ['numpy','pandas','sklearn','torch','streamlit','plotly','pykt.models.dkt','pyBKT.models']:
    importlib.import_module(module); print('PASS import '+module)
from core import CONFIG,paths,prediction_paths
for name in CONFIG:
    data,run,seed,_=paths(name)
    needed=[data/'test/histories.jsonl',run/f'dkt_seed{seed}_history.json',run/f'dkt_seed{seed}.ckpt',*prediction_paths(name).values()]
    missing=[p.relative_to(ROOT).as_posix() for p in needed if not p.exists()]
    print(json.dumps({'dataset':name,'artifacts':'MISSING (expected in clean clone)' if missing else 'PRESENT','missing':missing}))
print('For private artifacts see docs/ARTIFACT_SETUP.md; no fallback data are generated.')
