"""Tiny fabricated fixture for software checks ONLY, never benchmark evidence."""
import csv,hashlib,json,os,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.test_artifacts'/uuid.uuid4().hex
WORK.mkdir(parents=True)
raw=WORK/'fictional_fixture.csv'
fields=['user_id','order_id','problem_id','correct','skill_id','original','attempt_count','hint_count','ms_first_response']
with raw.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
    for uid in range(20):
        for t in range(4): w.writerow(dict(user_id=uid,order_id=uid*10+t,problem_id=t,correct=t%2,skill_id=1,original=1,attempt_count=1,hint_count=0,ms_first_response=100))
cfg=json.loads((ROOT/'experiments/assist2009_preparation/config.json').read_text())
cfg.update(input=raw.relative_to(ROOT).as_posix(),expected_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),encoding='utf-8')
config=WORK/'config.json';config.write_text(json.dumps(cfg))
def run(*args):
    result=subprocess.run([sys.executable,*map(str,args)],cwd=ROOT,check=True,capture_output=True,text=True)
    print('PASS '+str(args[0]));return result
run('scripts/check_setup.py')
run('experiments/assist2009_preparation/prepare.py','--config',config,'--output',WORK/'prepared')
run('scripts/train_dkt.py','--data',WORK/'prepared','--output',WORK/'trained','--max-epochs','1','--patience','1')
run('scripts/evaluate.py',WORK/'trained/predictions_dkt_seed42_test.csv')
sys.path.insert(0,str(ROOT/'kt_demo'))
from streamlit.testing.v1 import AppTest
for name in ['Skill Builder','Non-Skill Builder']:
    at=AppTest.from_file(str(ROOT/'kt_demo/app.py'),default_timeout=60).run()
    at.sidebar.selectbox[0].select(name).run()
    assert not at.exception and at.error and at.info
    assert 'ARTIFACT_SETUP.md' in at.info[0].value
print('PASS dashboard missing-artifact guidance for both datasets')
run('kt_demo/check_server.py')
(WORK/'smoke_result.json').write_text(json.dumps({'status':'PASS','fixture':'fictional; no research metrics','checks':['imports','preprocessing 80 fictional rows','one-epoch DKT and checkpoint reload','CSV evaluation','two missing-artifact dashboard paths','HTTP server']},indent=2))
