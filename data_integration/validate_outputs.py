#!/usr/bin/env python3
"""Validate real outputs and immutable source hashes; never imports models."""
import argparse
import subprocess
import sys
import tempfile
import csv
import hashlib
import hmac
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from preprocess import ROOT, FIELDS, EXTRA, INPUTS, read, sha

D=Path(__file__).resolve().parent/'normalized'
checks=[]
def check(condition,name):
    if not condition: raise AssertionError(name)
    checks.append(name)

def main():
    global D
    ap=argparse.ArgumentParser(description='Validate selected integration outputs; full private benchmark verification is opt-in.')
    ap.add_argument('--output', type=Path, default=D)
    ap.add_argument('--input-root', type=Path, default=ROOT)
    ap.add_argument('--key-file', type=Path, default=ROOT/'.local_data_integration/pseudonym.key')
    ap.add_argument('--benchmark', action='store_true', help='Also verify every original benchmark artifact and saved metric; requires private archive at repository paths')
    ap.add_argument('--benchmark-root', type=Path, default=ROOT, help='Unmodified original benchmark archive; used only with --benchmark')
    args=ap.parse_args(); D=args.output.resolve(); input_root=args.input_root.resolve()
    checks.clear()
    benchmark_root=args.benchmark_root.resolve()
    check(args.key_file.is_file() and args.key_file.stat().st_size>=32, 'existing HMAC key required; validator never creates a key')
    manifest=json.loads((D/'RUN_MANIFEST.json').read_text(encoding='utf-8'))
    for name in manifest['outputs']:
        check(Path(name).name == name, 'safe output manifest path')
    for rel in manifest['source_hashes']:
        check(not Path(rel).is_absolute() and '..' not in Path(rel).parts, 'safe source manifest path')
    for rel,h in manifest['source_hashes'].items(): check(sha(input_root/rel)==h,'unchanged source '+rel)
    for rel,h in manifest['outputs'].items(): check(sha(D/rel)==h,'output checksum '+rel)
    check(sha(Path(__file__).with_name('preprocess.py'))==manifest['script_sha256'],'adapter source checksum')
    if args.benchmark:
        for row in csv.DictReader((benchmark_root/'presentation/ARTIFACT_MANIFEST.csv').open(encoding='utf-8')):
            check(sha(benchmark_root/row['path'])==row['sha256'],'retained artifact '+row['path'])
    stats=json.loads((D/'AUDIT_STATS.json').read_text(encoding='utf-8'))
    for summary in stats['normalized']:
        n=0; eligible=0; rawcorrect=Counter()
        for _,r in read(D/summary['file']):
            n+=1
            checkset=set(FIELDS+EXTRA)==set(r)
            if not checkset: raise AssertionError('schema')
            if r['correct'] not in ('','0','1'): raise AssertionError('fabricated/fractional binary label')
            if summary['file'].startswith('daotao'):
                if r['correct'] or r['skill_id'] or r['kt_eligible']!='0': raise AssertionError('fabricated daotao KT label')
            if summary['file']=='assist2009_full.csv' and (r['skill_id'] or r['kt_eligible']!='0'):
                raise AssertionError('Full training gate')
            if r['kt_eligible']=='1':
                eligible+=1
                if not (r['correct'] in ('0','1') and r['skill_id'] and r['original']=='1' and r['split']): raise AssertionError('KT eligibility')
            if r['learner_id'] and not re.fullmatch(r'(assist2009|daotao_ai):learner:[0-9a-f]{24}',r['learner_id']): raise AssertionError('identity format')
            if summary['file'].startswith('assist'):
                if r['correct'] != (r['raw_correct'] if r['raw_correct'] in ('0','1') else ''): raise AssertionError('label transformation')
                rawcorrect[r['raw_correct']]+=1
        check(n==summary['records'] and eligible==summary['kt_eligible_events'],'row conservation / eligibility '+summary['file'])
        if summary['file'].startswith('assist'):
            check(dict(rawcorrect)==stats['assistments'][summary['file'][:-4]]['correct_distribution'],'label distribution conservation '+summary['file'])
    if stats.get('daotao') is not None:
        key=args.key_file.read_bytes()
        def pseudonym(raw): return 'daotao_ai:learner:'+hmac.new(key,('daotao_ai\0'+raw.strip()).encode(),hashlib.sha256).hexdigest()[:24]
        original=list(read(input_root/INPUTS[3][1])); normalized={int(r['source_record']):r for _,r in read(D/'daotao_activity_events.csv')}
        for n,r in original:
            e=normalized[n]
            check(e['learner_id']==pseudonym(r['Tên đăng nhập']),'activity identity consistent '+str(n))
            check(e['timestamp']==datetime.strptime(r['Thời gian'],'%d/%m/%Y %H:%M:%S').isoformat(),'observed timestamp '+str(n))
            if e['event_kind']=='answer_submission':
                match=re.search(r'(input_[0-9a-f]{32}_\d+_\d+)=(choice_\d+)',r['Hành động'])
                check(e['question_id']=='daotao_ai:input:'+match.group(1) and e['selected_answer']==match.group(2),'observed input/choice '+str(n))
        grades=list(read(input_root/INPUTS[4][1])); snapshots={int(r['source_record']):r for _,r in read(D/'daotao_grade_snapshots.csv')}
        for n,r in grades: check(snapshots[n]['learner_id']==pseudonym(r['Tên đăng nhập']),'grade identity consistent '+str(n))
        # Exact identities from the originals must not occur in exported daotao tables or human reports.
        secrets=set()
        for _,r in original: secrets.update([r['Tên đăng nhập'],r['Địa chỉ IP']])
        for _,r in grades: secrets.update([r['Tên đăng nhập'],r['Email'],r['Tên đầy đủ']])
        exports=list(D.glob('daotao*.csv'))+list((ROOT/'presentation').glob('*.md'))+list(Path(__file__).parent.glob('*.md'))
        for p in exports:
            content=p.read_text(encoding='utf-8')
            for secret in secrets:
                if secret and not secret.isdigit() and len(secret)>=4 and re.search(r'(?<!\w)'+re.escape(secret)+r'(?!\w)',content): raise AssertionError('Raw identity in '+p.name)
        check(True,'no literal nonnumeric learner identities in daotao exports or reports; identity fields checked via HMAC')
        events=[r for _,r in read(D/'daotao_activity_events.csv')]
        counts=Counter(); last={}; lastpair={}; behavior={r['event_id']:r for _,r in read(D/'daotao_behavior_observations.csv')}
        for e in events:
            u=e['learner_id'];pair=u,e['question_id']
            if u in last: check(last[u]['timestamp']<=e['timestamp'],'nondecreasing observed temporal sequence '+e['event_id'])
            if e['event_kind']=='answer_submission':
                b=behavior[e['event_id']]
                check(int(b['observed_prior_same_input_submissions'])==counts[pair],'strict prefix count '+e['event_id'])
                if pair in lastpair: check(int(b['answer_changed_from_previous_same_input'])==int(e['selected_answer']!=lastpair[pair]['selected_answer']),'observed choice switch '+e['event_id'])
                if u in last:
                    gap=(datetime.fromisoformat(e['timestamp'])-datetime.fromisoformat(last[u]['timestamp'])).total_seconds()
                    check(float(b['previous_observed_event_gap_seconds'])==gap,'observed event gap '+e['event_id'])
                counts[pair]+=1; lastpair[pair]=e
            last[u]=e
    if args.benchmark:
        results=list(csv.DictReader((benchmark_root/'presentation/RESULTS_COMPARISON.csv').open(encoding='utf-8')))
        check(len(results)==6 and len({r['benchmark'] for r in results})==2,'two benchmarks three methods')
        for r in results:
            m=json.loads((benchmark_root/r['metric_artifact']).read_text(encoding='utf-8'))
            key='baseline' if r['method']=='Skill-frequency baseline' else 'bkt' if r['method']=='BKT' else 'dkt_seed'+r['selected_seed']
            metric=m['metrics']['baseline_test'] if 'metrics' in m else next(x for x in m['rows'] if x['model']==key and x['split']=='test')
            check(all(float(r[k])==metric[k] for k in ['auc','accuracy','log_loss','brier']),'saved metric exactly copied '+r['benchmark']+' '+key)
    with tempfile.TemporaryDirectory(prefix='integration_verify_', dir=D) as temp:
        replay=Path(temp)/'replayed'
        command=[sys.executable, str(Path(__file__).with_name('preprocess.py')), '--sources',
                 *manifest.get('selected_sources', ['all']), '--input-root', str(input_root),
                 '--key-file', str(args.key_file.resolve()), '--output', str(replay)]
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        replay_manifest=json.loads((replay/'RUN_MANIFEST.json').read_text(encoding='utf-8'))
        check(set(replay_manifest['outputs'])==set(manifest['outputs']), 'complete selected output manifest')
        for name, digest in manifest['outputs'].items():
            check(sha(replay/name)==digest, 'source-driven canonical/summary consistency '+name)
    report=dict(status='PASS',mode='benchmark' if args.benchmark else 'integration',selected_sources=manifest.get('selected_sources',['all']),assertions_passed=len(checks),checks=checks,training_run=False,
                note='Real source/output invariants, no inference/training; per-record checks supplement these aggregate assertions')
    (D/'VALIDATION_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status='PASS',assertions_passed=len(checks),training_run=False)))

if __name__=='__main__':main()
