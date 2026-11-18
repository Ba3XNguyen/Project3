"""Regression checks on fictional inputs only; stdlib, no model or benchmark."""
import csv
import hashlib
import json
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'data_integration'))
from preprocess import INPUTS

def rows_at(path):
    with path.open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))

def csvfile(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.base=ROOT/'.test_artifacts'/('integration '+uuid.uuid4().hex)
        self.base.mkdir(parents=True)
        self.key=self.base/'private.key'

    def fixture(self,indices):
        for i in indices:
            if i<3:
                rows=[dict(user_id='9000001',order_id=str(n),problem_id='7',correct=str(n%2),skill_id='1',original='1',
                           assignment_id='9',attempt_count='1',hint_count='0',ms_first_response='100',list_skill_ids='1',ms_first_response_time='100') for n in (1,2)]
                csvfile(self.base/INPUTS[i][1],rows)
                if i<2:
                    cohort='assist2009_phase2a' if i==0 else 'assist2009_non_skill'
                    csvfile(self.base/'results'/cohort/'events.csv',[dict(r,source_record=n,split='train',common_target=str(n-1)) for n,r in enumerate(rows,1)])
            elif i==3:
                csvfile(self.base/INPUTS[i][1],[{'Thời gian':f'01/01/2026 10:00:0{n}','Tên đăng nhập':'fixture_learner',
                    'Hành động':'Gửi đáp án cho một câu hỏi. Id của câu hỏi là: input_'+'a'*32+'_2_1=choice_'+str(n),
                    'Địa chỉ IP':'','Trang tương tác':''} for n in (0,1)])
            else:
                csvfile(self.base/INPUTS[i][1],[{'ID':'9000001','Email':'','Tên đăng nhập':'fixture_learner','Tên đầy đủ':'',
                    'Trạng thái':'fixture','Điểm tổng':'1','Điểm tối đa':'1','Điểm quy đổi':'100','Câu 1':'1','Câu 2':'Chưa làm'}])

    def command(self,script,*args,ok=True):
        p=subprocess.run([sys.executable,str(ROOT/'data_integration'/script),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
        if ok:self.assertEqual(p.returncode,0,p.stderr)
        else:self.assertNotEqual(p.returncode,0)
        return p

    def preprocess(self,*sources):
        out=self.base/('normalized_'+uuid.uuid4().hex)
        self.command('preprocess.py','--sources',*sources,'--input-root',self.base,'--key-file',self.key,'--output',out)
        return out

    def validate(self,out,ok=True,benchmark=False):
        return self.command('validate_outputs.py','--output',out,'--input-root',self.base,'--key-file',self.key,*(['--benchmark'] if benchmark else []),ok=ok)

    def test_selected_sources_without_unrelated_inputs(self):
        for sources,indices in [(['skill'],[0]),(['non-skill'],[1]),(['assistments'],[0,1]),(['full'],[2]),(['daotao'],[3,4]),(['all'],list(range(5)))]:
            with self.subTest(sources=sources):
                self.setUp();self.fixture(indices);out=self.preprocess(*sources);self.validate(out)
                manifest=json.loads((out/'RUN_MANIFEST.json').read_text())
                self.assertEqual(manifest['source_names'],[INPUTS[i][0] for i in indices])

    def test_membership_required_before_writing(self):
        self.fixture([0]);(self.base/'results/assist2009_phase2a/events.csv').unlink()
        out=self.base/'missing'
        self.command('preprocess.py','--sources','skill','--input-root',self.base,'--output',out,'--key-file',self.key,ok=False)
        self.assertFalse(out.exists());self.assertFalse(self.key.exists())

    def test_corrupted_membership_rejected(self):
        self.fixture([0]);p=self.base/'results/assist2009_phase2a/events.csv'
        p.write_text(p.read_text(encoding='utf-8-sig').replace('9000001','9000002'),encoding='utf-8')
        self.command('preprocess.py','--sources','skill','--input-root',self.base,'--output',self.base/'bad','--key-file',self.key,ok=False)

    def test_output_tamper_even_with_updated_hash_rejected(self):
        self.fixture([3,4]);out=self.preprocess('daotao')
        p=out/'daotao_grade_snapshots.csv'
        rows=rows_at(p);rows[0]['obtained_score']='0';csvfile(p,rows)
        manifest=json.loads((out/'RUN_MANIFEST.json').read_text());manifest['outputs'][p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
        (out/'RUN_MANIFEST.json').write_text(json.dumps(manifest))
        self.validate(out,ok=False)

    def test_source_tamper_and_benchmark_opt_in(self):
        self.fixture([3,4]);out=self.preprocess('daotao');self.validate(out)
        self.validate(out,ok=False,benchmark=True)
        p=self.base/INPUTS[4][1];p.write_bytes(p.read_bytes()+b'\n');self.validate(out,ok=False)

    def test_validation_missing_key_fails_without_creating_key(self):
        self.fixture([0]);out=self.preprocess('skill')
        absent=self.base/'absent.key'
        self.command('validate_outputs.py','--output',out,'--input-root',self.base,'--key-file',absent,ok=False)
        self.assertFalse(absent.exists())

    def test_no_submission_and_no_numeric_grade(self):
        self.fixture([3,4]);p=self.base/INPUTS[3][1]
        rows=rows_at(p)
        for r in rows:r['Hành động']='Đăng ký khóa học.'
        csvfile(p,rows)
        p=self.base/INPUTS[4][1];rows=rows_at(p)
        for c in ('Điểm tổng','Điểm quy đổi','Câu 1'):rows[0][c]='Chưa làm'
        csvfile(p,rows);out=self.preprocess('daotao');self.validate(out)
        self.assertEqual(len(rows_at(out/'daotao_question_submissions.csv')),0)

if __name__=='__main__':unittest.main(verbosity=2)
