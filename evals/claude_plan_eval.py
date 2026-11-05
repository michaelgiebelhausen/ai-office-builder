"""Optional live, tool-free Claude planning eval, applied only to generated homes.
Run from repo root: python evals/claude_plan_eval.py --out evals/local-results
Claude receives only synthetic inputs and skill text; it has NO tools. The
harness validates every output path, executes approved manifests, then audits.
Not a substitute for Claude Desktop/Cowork installation testing.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from conftest import put, tree


def script(name,*args):
    result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'skill/ai-office-builder/scripts'/name),*map(str,args)],capture_output=True,text=True,encoding='utf-8',timeout=60)
    if result.returncode:
        raise RuntimeError(result.stdout+result.stderr)
    return result.stdout


def safe(base, relative):
    p=(base/relative).resolve()
    if p!=base and base not in p.parents:
        raise ValueError('Model output escaped fake home: '+relative)
    return p


def evaluate(scenario,out):
    with tempfile.TemporaryDirectory(prefix='ai-office-eval-') as tmp:
        home=Path(tmp).resolve()/'home';home.mkdir()
        root=home/'OneDrive/Cowork'
        sources=[]
        def source(path,text):
            p=put(home/path,text);sources.append(path)
        source('Desktop/Acme brief.txt','Synthetic Acme brief')
        source('Desktop/Birch brief.txt','Synthetic Birch brief')
        if scenario['mode']=='student':
            sources=[]
            # Keep all scenario sources relevant: both become side-hustle briefs.
            sources.extend(['Desktop/Acme brief.txt','Desktop/Birch brief.txt'])
            for course in scenario['answers']['courses']:
                source('Documents/'+course+' syllabus.txt',course+' current full text')
        source('Documents/article.txt','Captured general knowledge')
        source('Documents/AI report.txt','AI generated knowledge')
        put(home/'Desktop/app/.git/HEAD','ref: refs/heads/main')
        put(home/'Desktop/app/main.txt','synthetic repo')
        sources.append('Desktop/app')
        (home/'Code').mkdir()
        prior=''
        if scenario.get('resume'):
            tree(home,scenario['mode'])
            old=put(home/'Desktop/earlier.txt','Already moved; do not repeat')
            m=put(home/'earlier.json',json.dumps({'bundle':'01_completed','reference_roots':[str(home/'Desktop')],'dependency_review':'Synthetic scenario: no external consumers','moves':[{'src':str(old),'dst':'21_Acme/Resources/earlier.txt'}]}))
            script('move_bundle.py',m,'--cowork',root,'--dry-run')
            script('move_bundle.py',m,'--cowork',root)
            prior=(root/'00_Inbox/_migration/migration_log.md').read_text()
        inventory=home/'scan.json'
        script('scan.py',home/'Desktop',home/'Documents','--out',inventory)
        existing={p.relative_to(root).as_posix():p.read_text(encoding='utf-8') for p in root.rglob('*') if p.is_file()} if root.exists() else {}
        materials='\n\n'.join('FILE '+p.name+'\n'+p.read_text(encoding='utf-8') for p in [ROOT/'skill/ai-office-builder/SKILL.md',*sorted((ROOT/'skill/ai-office-builder/references').glob('*.md'))])
        prompt=materials+'\n\nEVALUATION REQUEST\nBuild my AI office using this skill. This is a synthetic scripted session. The interview answers, folder proposal and every source-to-destination bundle are approved for this evaluation. Do not ask questions. You have no tools: return JSON only with directories (paths relative to fake Cowork), files (object mapping relative Cowork path to full text), and moves (src relative to fake home, dst relative to fake Cowork, except code dst is the absolute fake-home Code/app path below). All directories needed must be listed or implied by files. Never replace existing files. Create substantive concise CLAUDE.md routing and context, no placeholder text. Use exactly the agent names implied by answers. Include every remaining source once. For student side-hustle, both briefs are Campus Design client work. Active course documents stay full text with their courses. Repositories move whole to Code, not into Cowork. Read the supplied existing log and continue only unfinished work. Files already present need not be emitted again.\n'+json.dumps({'scenario':scenario,'inventory':json.loads(inventory.read_text()),'home':str(home),'cowork':str(root),'code_repo_destination':str(home/'Code/app'),'remaining_sources':sources,'existing_files':existing,'migration_log':prior})
        response=subprocess.run([shutil.which('claude'),'--safe-mode','--tools','','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--no-session-persistence','--output-format','json','-p'],input=prompt,cwd=home,capture_output=True,text=True,encoding='utf-8',timeout=300)
        if response.returncode:
            raise RuntimeError(response.stdout+response.stderr)
        envelope=json.loads(response.stdout)
        text=envelope['result'].strip()
        if text.startswith('```'):
            text=text.split('\n',1)[1].rsplit('```',1)[0]
        plan=json.loads(text)
        out.mkdir(parents=True,exist_ok=True)
        put(out/(scenario['id']+'-plan.json'),json.dumps(plan,indent=2))
        for d in plan['directories']:
            safe(root,d).mkdir(parents=True,exist_ok=True)
        for p,content in plan['files'].items():
            target=safe(root,p)
            if target.exists():
                raise ValueError('Model tried to overwrite '+p)
            put(target,content)
        rows=[]
        assert sorted(r['src'] for r in plan['moves'])==sorted(sources),'Missing or repeated source in model plan'
        for row in plan['moves']:
            s=safe(home,row['src'])
            if Path(row['dst']).is_absolute():
                d=Path(row['dst']).resolve()
                assert d==home/'Code/app'
            else:
                d=safe(root,row['dst'])
            rows.append({'src':str(s),'dst':str(d)})
        manifest=put(home/'approved.json',json.dumps({'bundle':'02_model_approved','reference_roots':[str(home/'Desktop'),str(home/'Documents')],'dependency_review':'Synthetic scenario: no external consumers; application formats reviewed','moves':rows}))
        script('move_bundle.py',manifest,'--cowork',root,'--dry-run')
        script('move_bundle.py',manifest,'--cowork',root)
        audit=home/'audit.json'
        result=script('audit.py',root,'--mode',scenario['mode'],'--code',home/'Code','--json',audit)
        assert all(not safe(home,s).exists() for s in sources)
        assert (home/'Code/app/.git/HEAD').read_text()=='ref: refs/heads/main'
        if prior:
            assert (root/'00_Inbox/_migration/migration_log.md').read_text().startswith(prior)
            assert (root/'21_Acme/Resources/earlier.txt').read_text()=='Already moved; do not repeat'
        summary={'scenario':scenario['id'],'pass':True,'audit':json.loads(audit.read_text()),'moved_items':len(rows),'model':envelope.get('modelUsage',{}),'scope':'tool-free Claude planning, harness execution, final audit; not Desktop UI'}
        # Do not retain machine-specific fake-home paths or account metadata.
        summary.pop('model')
        put(out/(scenario['id']+'-result.json'),json.dumps(summary,indent=2))
        print(scenario['id']+': PASS ('+str(len(rows))+' items)',flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    for scenario in json.loads((ROOT/'evals/scenarios.json').read_text()):
        evaluate(scenario,a.out.resolve())
