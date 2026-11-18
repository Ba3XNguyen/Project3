"""Read-only Non-Skill-Builder adapter for the shared KT protocol."""
import csv, hashlib, json, random, re
from collections import Counter, defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; RAW=ROOT/'data/assistment_2009/non_skill_builder_data_new.csv'
OUT=ROOT/'results/assist2009_non_skill'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 if (OUT/'dataset_manifest.json').exists(): raise RuntimeError('refuse overwrite')
 raw_sha=sha(RAW); events=[]; excluded=Counter(); audit=Counter(); skills_raw=set(); users_raw=set(); problems_raw=set(); order_seen=set(); prev={}; decreases=0; pair=Counter(); correct=Counter(); original=Counter(); multi=Counter()
 with RAW.open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f); columns=reader.fieldnames
  for rec,row in enumerate(reader,1):
   audit['raw']+=1; uid=row['user_id'].strip(); oid=row['order_id'].strip(); pid=row['problem_id'].strip(); sk=row['skill_id'].strip(); c=row['correct'].strip(); orig=row['original'].strip(); users_raw.add(uid);problems_raw.add(pid);correct[c]+=1;original[orig]+=1
   if oid in order_seen: audit['duplicate_order_id']+=1
   order_seen.add(oid)
   if uid and oid.isdigit():
    oi=int(oid)
    if uid in prev and oi<prev[uid]: decreases+=1
    prev[uid]=oi
   pair[uid,pid]+=1
   if sk: skills_raw.add(sk)
   if ',' in sk: multi['comma_multiskill']+=1
   checks=[uid.isdigit() and oid.isdigit() and pid.isdigit(),'0'<=c<='1' and c in {'0','1'},bool(sk),bool(re.fullmatch(r'\d+',sk)),orig=='1']
   reasons=['required_numeric','binary_correct','skill_present','single_numeric_skill','original_main']
   bad=next((reasons[i] for i,x in enumerate(checks) if not x),None)
   if bad: excluded[bad]+=1; continue
   events.append({'event_id':f'non_skill:{oid}','source_record':rec,'user_id':int(uid),'order_id':int(oid),'problem_id':int(pid),'skill_id':sk,'correct':int(c),'original':1})
 events.sort(key=lambda e:(e['user_id'],e['order_id'])); users=sorted({e['user_id'] for e in events}); random.Random(42).shuffle(users); ntr=int(.70*len(users));nv=int(.15*len(users)); split={u:'train' for u in users[:ntr]}|{u:'validation' for u in users[ntr:ntr+nv]}|{u:'test' for u in users[ntr+nv:]}
 mapping={s:i for i,s in enumerate(sorted({e['skill_id'] for e in events if split[e['user_id']]=='train'},key=int))}; grouped=defaultdict(list)
 for e in events:
  e['split']=split[e['user_id']];e['skill_idx']=mapping.get(e['skill_id']);e['common_target']=int(e['skill_idx'] is not None and len(grouped[e['user_id']])>0);e['target_reason']='eligible' if e['common_target'] else ('first_known_interaction' if e['skill_idx'] is not None else 'oov_skill');
  if e['skill_idx'] is not None: grouped[e['user_id']].append(e)
 OUT.mkdir(parents=True,exist_ok=True)
 def write_csv(path,fields,rows):
  with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
 write_csv(OUT/'events.csv',list(events[0]),events); write_csv(OUT/'excluded_counts.csv',['reason','count'],[{'reason':k,'count':v} for k,v in excluded.items()])
 with (OUT/'histories.jsonl').open('w') as f:
  for u in sorted(grouped):f.write(json.dumps({'uid':u,'split':split[u],'events':grouped[u]},separators=(',',':'))+'\n')
 targets=[]
 for e in events: targets.append({'event_id':e['event_id'],'split':e['split'],'common_target':e['common_target'],'correct':e['correct']})
 write_csv(OUT/'target_eligibility.csv',list(targets[0]),targets)
 for s in ('train','validation','test'):
  folder=OUT/s;folder.mkdir(exist_ok=True); split_users=sorted(u for u in grouped if split[u]==s); rows=[e for e in events if e['split']==s and e['skill_idx'] is not None]
  write_csv(folder/'pybkt.csv',['event_id','user_id','order_id','skill_id','correct','original'],rows)
  with (folder/'histories.jsonl').open('w') as f:
   for u in split_users:f.write(json.dumps({'uid':u,'events':grouped[u]},separators=(',',':'))+'\n')
  seq=[]
  for u in split_users:
   ev=grouped[u]
   for st in range(0,len(ev),200):
    ch=ev[st:st+200]; pad=200-len(ch); seq.append({'fold':{'train':1,'validation':0,'test':-1}[s],'uid':u,'concepts':','.join([str(e['skill_idx']) for e in ch]+['-1']*pad),'responses':','.join([str(e['correct']) for e in ch]+['-1']*pad),'selectmasks':','.join(['1']*len(ch)+['-1']*pad),'event_ids':','.join([e['event_id'] for e in ch]+['PAD']*pad)})
  write_csv(folder/'dkt_sequences.csv',list(seq[0]),seq)
  audit[f'{s}_users']=len(split_users);audit[f'{s}_events']=len(rows);audit[f'{s}_targets']=sum(e['common_target'] for e in rows)
 audit=dict(audit)
 audit.update({'raw_rows':sum(correct.values()),'raw_columns':columns,'raw_sha256':raw_sha,'raw_users':len(users_raw),'raw_problems':len(problems_raw),'raw_skills_strings':len(skills_raw),'raw_correct_counts':dict(correct),'raw_original_counts':dict(original),'raw_duplicate_order_id':audit.get('duplicate_order_id',0),'raw_order_decreases_within_user':decreases,'raw_repeated_user_problem_extra_events':sum(v-1 for v in pair.values() if v>1),'raw_multiskill_comma_rows':multi['comma_multiskill'],'valid_events':len(events),'users':len({e['user_id'] for e in events}),'skills':len({e['skill_id'] for e in events}),'train_mapped_skills':len(mapping),'filter_excluded':dict(excluded),'encoding':'utf-8-sig','split_seed':42,'split_rule':'user-disjoint 70/15/15; floor train/validation, remainder test','single_skill_policy':'keep digit-only skill_id; exclude comma multi-skill; no expansion','behavior_predictors':False})
 (OUT/'data_quality.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n');(OUT/'skill_mapping.json').write_text(json.dumps({'fitted_on':'train','skill_to_idx':mapping,'num_c':len(mapping),'oov_policy':'exclude from context and target'},indent=2)+'\n');(OUT/'split_manifest.json').write_text(json.dumps({'seed':42,'users':{s:sorted(u for u in split if split[u]==s) for s in ('train','validation','test')}},indent=2)+'\n');(OUT/'dataset_manifest.json').write_text(json.dumps({'phase':'4A','raw':{'path':'data/assistment_2009/non_skill_builder_data_new.csv','sha256':raw_sha,'bytes':RAW.stat().st_size},'valid_events':len(events),'users':len({e['user_id'] for e in events}),'skills':len(mapping),'models_trained':[]},indent=2)+'\n')
 print(json.dumps({'events':len(events),'users':len({e['user_id'] for e in events}),'skills':len(mapping),'excluded':dict(excluded)},indent=2))
if __name__=='__main__':main()
