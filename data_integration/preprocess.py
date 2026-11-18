#!/usr/bin/env python3
"""Read-only source adapters. Python stdlib only; no model import or training.
A new output directory is required on each run. Raw inputs are never written.
"""
import argparse
import csv
import hashlib
import hmac
import json
import os
import re
import secrets
from collections import Counter, defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FIELDS = 'source learner_id course_id assessment_id question_id skill_id correct interaction_order timestamp selected_answer response_time_ms attempt_count hint_count max_score obtained_score'.split()
EXTRA = 'event_id source_record event_kind question_id_basis timestamp_timezone_status raw_skill_ids raw_correct original observed_assignment_id split common_target kt_eligible exclusion_reason'.split()
MISSING = {'', 'nan', 'na', 'null', 'none', 'chưa làm'}
INPUTS = [
 ('assist2009_skill_builder', 'data/assistment_2009/skill_builder_data_corrected_collapsed.csv', 'cp1252'),
 ('assist2009_non_skill_builder', 'data/assistment_2009/non_skill_builder_data_new.csv', 'utf-8-sig'),
 ('assist2009_full', 'data/assistment_2009/full_dataset.csv', 'utf-8-sig'),
 ('daotao_activity', 'data/daotao_ai/Activity Log at 134621 6112026.csv', 'utf-8-sig'),
 ('daotao_grades', 'data/daotao_ai/Visual Grades Report at 134113 6112026.csv', 'utf-8-sig')]

def clean(x):
    x = (x or '').strip()
    return '' if x.lower() in MISSING else x

def number(x):
    x = clean(x)
    if not x: return ''
    try:
        v = float(x)
        return x if v >= 0 and v < float('inf') else ''
    except ValueError: return ''

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def read(p, encoding='utf-8-sig'):
    with p.open(encoding=encoding, newline='') as f:
        r = csv.DictReader(f)
        if len(r.fieldnames) != len(set(r.fieldnames)): raise ValueError('Duplicate header')
        for n, row in enumerate(r, 1):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'Malformed CSV record {n} in {p.name}')
            yield n, row

def write(p, fields, rows):
    with p.open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)

class Export:
    def __init__(self, out):
        self.out, self.stats, self.missing = out, [], []

    def emit(self, name, rows):
        count = 0; missing = Counter(); eligible = Counter(); users = set(); questions = set()
        usable_user = Counter(); reasons = Counter()
        with (self.out / name).open('x', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS+EXTRA, extrasaction='raise'); w.writeheader()
            for row in rows:
                count += 1
                for k in FIELDS: missing[k] += not clean(str(row.get(k, '')))
                if row.get('learner_id'): users.add(row['learner_id'])
                if row.get('question_id'): questions.add(row['question_id'])
                if row.get('kt_eligible') == 1:
                    eligible['events'] += 1; usable_user[row['learner_id']] += 1
                else: reasons[row.get('exclusion_reason', '')] += 1
                w.writerow(row)
        targets = sum(max(n-1, 0) for n in usable_user.values())
        self.stats.append(dict(file=name, records=count, learners=len(users), questions=len(questions),
                               kt_eligible_events=eligible['events'], next_step_candidates_before_split_oov=targets,
                               eligible_learners_with_2plus=sum(n >= 2 for n in usable_user.values()),
                               exclusions=dict(reasons)))
        self.missing.extend(dict(file=name, field=k, records=count, missing_count=missing[k],
                                 missing_rate=missing[k]/count if count else '') for k in FIELDS)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=ROOT/'data_integration/normalized')
    ap.add_argument('--key-file', type=Path, default=ROOT/'.local_data_integration/pseudonym.key')
    ap.add_argument('--sources', nargs='+', choices=['skill', 'non-skill', 'assistments', 'full', 'daotao', 'all'], default=['assistments'],
                    help='assistments=Skill+Non-Skill only; Full is opt-in. daotao requires both exports.')
    ap.add_argument('--input-root', type=Path, default=ROOT, help='Root containing data/ and results/; defaults to repository root')
    args = ap.parse_args(); out = args.output.resolve(); keyfile = args.key_file.resolve()
    input_root = args.input_root.resolve()
    groups = {'skill': [0], 'non-skill': [1], 'assistments': [0, 1], 'full': [2], 'daotao': [3, 4], 'all': list(range(5))}
    selected_indices = sorted({i for source in args.sources for i in groups[source]})
    selected = [INPUTS[i] for i in selected_indices]
    dependencies = [p for _, p, _ in selected]
    for i, cohort in [(0, 'assist2009_phase2a'), (1, 'assist2009_non_skill')]:
        if i in selected_indices: dependencies.append('results/'+cohort+'/events.csv')
    protected = [ROOT/'data', ROOT/'results', ROOT/'code', ROOT/'experiments', ROOT/'research_audit', ROOT/'survey', input_root/'data', input_root/'results']
    if any(out == p or p in out.parents or keyfile == p or p in keyfile.parents for p in protected):
        raise ValueError('Output/key must be outside original source and artifacts')
    if out.exists(): raise FileExistsError('Use a NEW --output directory; refusing overwrite')
    if out == keyfile or out in keyfile.parents: raise ValueError('Key must be outside exported directory')
    missing_inputs = [p for p in dependencies if not (input_root/p).is_file()]
    if missing_inputs: raise FileNotFoundError('Missing real inputs: '+', '.join(missing_inputs))
    before = {p: sha(input_root/p) for p in dependencies}
    keyfile.parent.mkdir(parents=True, exist_ok=True)
    if not keyfile.exists():
        fd = os.open(keyfile, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as f: f.write(secrets.token_bytes(32))
    key = keyfile.read_bytes()
    if len(key) < 32: raise ValueError('HMAC key must have >=32 bytes')
    @lru_cache(maxsize=100000)
    def learner(domain, raw):
        if not clean(raw): return ''
        return domain+':learner:'+hmac.new(key, (domain+'\0'+raw.strip()).encode(), hashlib.sha256).hexdigest()[:24]
    out.mkdir(parents=True); exporter = Export(out); raw_audit = {}; orders = {}
    for source, rel, enc in [item for item in selected if item[0].startswith('assist')]:
        raw_missing = Counter(); meta = {}; ids = set(); users = set(); questions = set(); raw_labels = Counter()
        full = source.endswith('_full')
        cohort = 'assist2009_non_skill' if 'non_skill' in source else 'assist2009_phase2a'
        # Read historical split membership, do not fit a new split/mapping or change labels.
        membership = {}
        membership_events = {}
        if not full:
            for _,e in read(input_root/'results'/cohort/'events.csv'):
                if int(e['source_record']) in membership: raise ValueError('Duplicate source_record in membership')
                membership[int(e['source_record'])] = (e['split'], e['common_target'])
                membership_events[int(e['source_record'])] = e
        def events():
            for n,r in read(input_root/rel, enc):
                if not meta: meta.update(columns=list(r), encoding=enc)
                raw_missing.update(k for k,v in r.items() if not clean(v))
                uid, oid, qid = (clean(r[k]) for k in ('user_id','order_id','problem_id'))
                if oid in ids: raise ValueError('Duplicate order_id; refuse ambiguous ordering')
                ids.add(oid); users.add(uid); questions.add(qid)
                skill = clean(r.get('list_skill_ids' if full else 'skill_id'))
                c = clean(r['correct']); raw_labels[c] += 1
                good_skill = bool(re.fullmatch(r'\d+', skill))
                reasons = []
                if not all(x.isdigit() for x in (uid,oid,qid)): reasons.append('invalid_keys')
                if c not in ('0','1'): reasons.append('nonbinary_correct')
                if not good_skill: reasons.append('missing_or_multiskill')
                if clean(r['original']) != '1': reasons.append('not_original')
                if full: reasons.append('full_skill_semantics_unverified')
                split, target = membership.get(n, ('',''))
                if not full and (not reasons) != (n in membership):
                    raise AssertionError('Canonical cohort differs from historical benchmark')
                if n in membership_events:
                    e = membership_events[n]
                    if any(clean(e[k]) != clean(r[k]) for k in ('user_id','order_id','problem_id','skill_id','correct','original')):
                        raise AssertionError('Membership event does not match raw source record')
                    if e['split'] not in ('train','validation','test') or e['common_target'] not in ('0','1'):
                        raise AssertionError('Invalid membership split/target')
                yield dict(source=source, learner_id=learner('assist2009', uid), question_id=source+':problem:'+qid,
                    skill_id=source+':skill:'+skill if good_skill and not full else '', correct=c if c in ('0','1') else '',
                    interaction_order=oid if oid.isdigit() else '', response_time_ms=number(r.get('ms_first_response_time' if full else 'ms_first_response')),
                    attempt_count=number(r.get('attempt_count')), hint_count=number(r.get('hint_count')),
                    event_id=source+':order:'+oid, source_record=n, event_kind='response', question_id_basis='problem_id',
                    raw_skill_ids=skill, raw_correct=c, original=clean(r['original']), observed_assignment_id=clean(r['assignment_id']),
                    split=split, common_target=target, kt_eligible=int(not reasons), exclusion_reason=';'.join(reasons))
        exporter.emit(source+'.csv', events())
        if membership and max(membership) > sum(raw_labels.values()): raise AssertionError('Membership references missing raw record')
        raw_audit[source] = dict(**meta, rows=sum(raw_labels.values()), learners=len(users), questions=len(questions),
                                correct_distribution=dict(raw_labels), missing=dict(raw_missing))
        orders[source] = ids
    overlap = []
    for a,b in [(INPUTS[0][0],INPUTS[1][0]),(INPUTS[0][0],INPUTS[2][0]),(INPUTS[1][0],INPUTS[2][0])]:
        if a not in orders or b not in orders: continue
        overlap.append(dict(source_a=a, source_b=b, shared_order_ids=len(orders[a]&orders[b]), policy='never concatenate'))
    del orders
    audit = None
    if 3 in selected_indices:
        activity = list(read(input_root/INPUTS[3][1])); grades = list(read(input_root/INPUTS[4][1]))
        if not activity or not grades: raise ValueError('Selected daotao exports must have at least one record each')
        actions = Counter(); log_events=[]; log_users=set(); submit_users=set(); times=[]
        for n,r in activity:
            a=r['Hành động']; uid=learner('daotao_ai',r['Tên đăng nhập']); log_users.add(uid)
            if a.startswith('Gửi đáp án cho một câu hỏi.'):
                kind='answer_submission'
            elif a=='Tạo báo cáo điểm của học viên.': kind='grade_report_created'
            elif a=='Đăng ký khóa học.': kind='course_enrollment'
            elif a=='Hủy đăng ký khóa học.': kind='course_unenrollment'
            else: kind='unclassified'
            actions[kind]+=1
            dt=datetime.strptime(r['Thời gian'].strip(), '%d/%m/%Y %H:%M:%S'); times.append(dt)
            payload=re.fullmatch(r'Gửi đáp án cho một câu hỏi\.\s*Id của câu hỏi là:\s*(input_[0-9a-f]{32}_\d+_\d+)=(choice_\d+)\s*',a)
            page=r['Trang tương tác']; course=re.search(r'/courses/([^/]+)/',page)
            if kind=='answer_submission': submit_users.add(uid)
            log_events.append(dict(source='daotao_ai',learner_id=uid,
                course_id='daotao_ai:'+unquote(course.group(1)) if course else '',
                question_id='daotao_ai:input:'+payload.group(1) if payload else '',
                selected_answer=payload.group(2) if payload else '', timestamp=dt.isoformat(),
                event_id=f'daotao_ai:activity:record:{n}',source_record=n,event_kind=kind,
                question_id_basis='observed_input_id_component_unverified' if payload else '',
                timestamp_timezone_status='unknown_export_timezone',kt_eligible=0,
                exclusion_reason='missing_verified_correct;missing_skill'))
        # File order is not trusted. Ties would remain explicitly flagged; no elapsed time is response time.
        log_events.sort(key=lambda e:(e['learner_id'],e['timestamp'],e['source_record']))
        counters=Counter(); repeated=Counter(); last={}; behavioral=[]
        for e in log_events:
            uid=e['learner_id']; counters[uid]+=1; e['interaction_order']=counters[uid]
            if e['event_kind']=='answer_submission':
                pair=(uid,e['question_id']); repeated[pair]+=1
                prev=last.get(uid); gap=(datetime.fromisoformat(e['timestamp'])-datetime.fromisoformat(prev['timestamp'])).total_seconds() if prev else ''
                behavioral.append(dict(event_id=e['event_id'],learner_id=uid,observed_submission_index=counters[uid],
                    observed_prior_same_input_submissions=repeated[pair]-1,previous_observed_event_gap_seconds=gap,
                    answer_changed_from_previous_same_input=int(e['selected_answer'] != last[pair]['selected_answer']) if pair in last else '',
                    session_gap_gt_30min=int(gap>1800) if gap!='' else ''))
                last[pair]=e
            last[uid]=e
        exporter.emit('daotao_activity_events.csv',log_events)
        exporter.emit('daotao_question_submissions.csv',(e for e in log_events if e['event_kind']=='answer_submission'))
        write(out/'daotao_behavior_observations.csv',['event_id','learner_id','observed_submission_index','observed_prior_same_input_submissions','previous_observed_event_gap_seconds','answer_changed_from_previous_same_input','session_gap_gt_30min'],behavioral)
        snapshots=[]; scorecells=[]; grade_users=set(); numeric_users=set(); cell_missing=Counter(); label_values=Counter(); total_checks=[]
        for n,r in grades:
            uid=learner('daotao_ai',r['Tên đăng nhập'])
            if uid in grade_users: raise ValueError('Duplicate grades username; ambiguous snapshot')
            grade_users.add(uid); total=number(r['Điểm tổng']); maximum=number(r['Điểm tối đa'])
            if total: numeric_users.add(uid)
            snapshots.append(dict(source='daotao_ai',learner_id=uid,obtained_score=total,max_score=maximum,
                event_id=f'daotao_ai:grade_snapshot:record:{n}',source_record=n,event_kind='aggregate_grade_snapshot',
                kt_eligible=0,exclusion_reason='aggregate_snapshot_not_interaction'))
            cell_sum=0
            for col in list(r)[8:]:
                val=number(r[col]); cell_missing[col]+=not bool(val)
                if val=='': continue
                cell_sum+=float(val); label_values[val]+=1
                scorecells.append(dict(source='daotao_ai',learner_id=uid,obtained_score=val,
                    event_id=f'daotao_ai:grade_cell:{n}:{list(r).index(col)}',source_record=n,
                    event_kind='component_grade_snapshot',kt_eligible=0,
                    exclusion_reason='unmapped_component;no_attempt_link;no_skill',
                    component_label=col))
            if total:
                total_checks.append(abs(float(total)-cell_sum)<1e-9 and abs(float(r['Điểm quy đổi'])-100*float(total)/float(maximum))<=0.0051)
        exporter.emit('daotao_grade_snapshots.csv',snapshots)
        # Safe, observed report labels are metadata, never invented question IDs.
        write(out/'daotao_component_score_snapshots.csv',FIELDS+EXTRA+['component_label'],scorecells)
        exporter.emit('daotao_component_scores_canonical.csv',({k:v for k,v in e.items() if k!='component_label'} for e in scorecells))
        grade_summary=dict(rows=len(grades), learners=len(grade_users), numeric_total_learners=len(numeric_users),
            numeric_component_cells=len(scorecells), component_cells=len(grades)*len(list(grades[0][1])[8:]),
            component_missing=dict(cell_missing), component_score_distribution=dict(label_values),
            all_numeric_totals_equal_component_sum_and_percent=all(total_checks), verified_totals=len(total_checks))
        audit=dict(activity_rows=len(activity),activity_columns=list(activity[0][1]),grades_columns=list(grades[0][1]),
            activity_event_types=dict(actions),activity_learners=len(log_users),submission_learners=len(submit_users),
            submission_counts_per_learner=sorted(Counter(e['learner_id'] for e in log_events if e['event_kind']=='answer_submission').values()),
            distinct_observed_input_ids=len({e['question_id'] for e in log_events if e['question_id']}),
            parsed_submission_rows=sum(bool(e['question_id']) for e in log_events),
            activity_time_min=min(times).isoformat(),activity_time_max=max(times).isoformat(),
            duplicate_learner_timestamps=sum(n-1 for n in Counter((e['learner_id'],e['timestamp']) for e in log_events).values()),
            users_shared_between_exports=len(log_users&grade_users), submission_users_with_numeric_totals=len(submit_users&numeric_users),
            verified_event_grade_joins=0,kt_eligible_daotao_events=0,grades=grade_summary)
    write(out/'MISSINGNESS.csv',['file','field','records','missing_count','missing_rate'],exporter.missing)
    write(out/'KT_ELIGIBILITY.csv',['file','records','learners','questions','kt_eligible_events','next_step_candidates_before_split_oov','eligible_learners_with_2plus'],exporter.stats)
    write(out/'SOURCE_OVERLAP.csv',['source_a','source_b','shared_order_ids','policy'],overlap)
    (out/'AUDIT_STATS.json').write_text(json.dumps(dict(daotao=audit,assistments=raw_audit,normalized=exporter.stats),ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    after={p:sha(input_root/p) for p in dependencies}
    if before!=after: raise AssertionError('Source changed during run')
    manifest=dict(script_sha256=sha(Path(__file__)),python=__import__('sys').version,
        selected_sources=args.sources, source_names=[x[0] for x in selected],
        source_hashes=before,source_hashes_unchanged=True,training_run=False,
        pseudonymization='HMAC-SHA256 truncated to 96 bits; secret kept outside exports; no raw identity map',
        outputs={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    (out/'RUN_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(daotao=audit,normalized=exporter.stats,overlap=overlap),ensure_ascii=True,indent=2))

if __name__=='__main__': main()
