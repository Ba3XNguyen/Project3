"""Audit the actual Git candidate list; does not add, commit, or push."""
import json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def git(*args): return subprocess.check_output(['git','-C',str(ROOT),*args])
def main():
    paths=sorted(set(git('ls-files','--cached','--others','--exclude-standard','-z').decode().split('\0'))-{''})
    failures=[]; reviewed_emails=set(); sizes=[]
    blocked={'data','results','.venv','.local_data_integration','.staging','.test_artifacts','__pycache__'}
    for rel in paths:
        p=ROOT/rel
        if p.is_symlink(): failures.append([rel,'symlink'])
        if rel not in {'data/README.md','results/README.md'} and any(x in blocked or x=='.git' for x in p.relative_to(ROOT).parts): failures.append([rel,'private/generated path'])
        if p.suffix in {'.ckpt','.pt','.pth','.pkl','.key','.pem','.pdf','.zip'}: failures.append([rel,'excluded artifact type'])
        size=p.stat().st_size;sizes.append((size,rel))
        if size>2_000_000: failures.append([rel,'unexpected large file'])
        try: text=p.read_text(encoding='utf-8-sig')
        except UnicodeError: failures.append([rel,'unexpected binary']);continue
        # Print only path/type of any finding, never matched token.
        patterns={'private_absolute_path':r'(?:[A-Za-z]:[\\/](?:Users|Vscode)|/home/\w+/)',
                  'private_key':r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',
                  'github_token':r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}',
                  'openai_token':r'\bsk-[A-Za-z0-9_-]{25,}',
                  'aws_key':r'\bAKIA[A-Z0-9]{16}\b'}
        for label,pattern in patterns.items():
            if re.search(pattern,text):failures.append([rel,label])
        for email in re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',text):
            if not rel.startswith('code/'):failures.append([rel,'email outside third-party attribution'])
            else: reviewed_emails.add(rel)
    probes=['data/private.csv','results/run/predictions_test.csv','.local_data_integration/pseudonym.key','.env','.venv/test','cache/__pycache__/a.pyc','model.ckpt','data_integration/normalized/events.csv']
    for probe in probes:
        if subprocess.run(['git','-C',str(ROOT),'check-ignore','-q',probe]).returncode!=0:failures.append([probe,'ignore probe failed'])
    modes=git('ls-files','--stage').decode()
    if any(line.startswith('160000 ') for line in modes.splitlines()):failures.append(['index','nested gitlink'])
    for folder in (ROOT/'code').rglob('.git'):failures.append([str(folder.relative_to(ROOT)),'nested git metadata'])
    result={'status':'PASS' if not failures else 'FAIL','candidate_files':len(paths),'candidate_bytes':sum(x[0] for x in sizes),
            'largest_files':[{'path':p,'bytes':n} for n,p in sorted(sizes,reverse=True)[:8]],
            'ignore_probes':len(probes),'third_party_attribution_email_files':sorted(reviewed_emails),'findings':failures,
            'scope':'Pattern/filename audit, not a proof of absence of every possible secret. Review candidate list before push.'}
    print(json.dumps(result,indent=2))
    if failures:raise SystemExit(1)
if __name__=='__main__':main()
