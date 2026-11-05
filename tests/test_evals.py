"""Scripted workflow replays. Fixtures are generated per test, never real homes.
These prove script integration, not conversational Claude quality; see evals/README.
"""
import json
from conftest import ROOT, put, tree
from test_scripts import manifest
import pytest

SCENARIOS=json.loads((ROOT/'evals/scenarios.json').read_text())


@pytest.mark.parametrize('scenario',SCENARIOS,ids=lambda s:s['id'])
def test_scenario(engine,tmp_path,scenario):
    home=tmp_path/'home'
    root=tree(home,scenario['mode'])
    desktop=home/'Desktop';docs=home/'Documents'
    put(desktop/'app/.git/HEAD','ref: refs/heads/main')
    put(desktop/'app/main.txt','synthetic repository')
    put(docs/'captured article.txt','captured knowledge')
    put(docs/'AI report.txt','AI generated knowledge')
    put(desktop/'unclassified.txt','sort later')
    rows=[{'src':str(desktop/'unclassified.txt'),'dst':'00_Inbox/to_sort/unclassified.txt'},
          {'src':str(docs/'captured article.txt'),'dst':'01_Library/raw_human/captured article.txt'},
          {'src':str(docs/'AI report.txt'),'dst':'01_Library/raw_AI/AI report.txt'}]
    client='21_Campus_Design' if scenario['mode']=='student' else '21_Acme'
    put(desktop/'client brief.txt','approved client brief')
    rows.append({'src':str(desktop/'client brief.txt'),'dst':client+'/Projects/2026_Q4_Launch/01_brief/client brief.txt'})
    if scenario['mode']=='student':
        for course in scenario['answers']['courses']:
            p=put(desktop/(course+' syllabus.txt'),course+' full text')
            rows.append({'src':str(p),'dst':'10_Class/'+course+'/Resources/'+p.name})
    else:
        put(desktop/'Birch brief.txt','Birch work')
        rows.append({'src':str(desktop/'Birch brief.txt'),'dst':'22_Birch/Projects/2026_Q4_Launch/01_brief/Birch brief.txt'})
    put(desktop/'extra article.txt','captured knowledge')
    rows.append({'src':str(desktop/'extra article.txt'),'dst':'00_Inbox/_duplicates/extra article.txt','note':'exact duplicate of captured article'})
    log=root/'00_Inbox/_migration/migration_log.md'
    if scenario.get('resume'):
        earlier=manifest(tmp_path,rows[:3],'01_completed')
        r=engine('move_bundle',earlier,'--cowork',root,'--dry-run');assert r.returncode==0,r.stdout+r.stderr
        r=engine('move_bundle',earlier,'--cowork',root);assert r.returncode==0,r.stdout+r.stderr
        before=log.read_bytes()
        undo_before=(root/'00_Inbox/_migration/undo_01_completed.json').read_bytes()
        assert '01_completed' in log.read_text(encoding='utf-8-sig')
        rows=rows[3:]
    out=tmp_path/'scan.json'
    r=engine('scan',desktop,docs,'--out',out);assert r.returncode==0,r.stdout+r.stderr
    code_bundle=manifest(tmp_path,[{'src':str(desktop/'app'),'dst':str(home/'Code/app')}],'02_code')
    next_bundle=manifest(tmp_path,rows,'03_remaining')
    for m in [code_bundle,next_bundle]:
        r=engine('move_bundle',m,'--cowork',root,'--dry-run');assert r.returncode==0,r.stdout+r.stderr
        r=engine('move_bundle',m,'--cowork',root);assert r.returncode==0,r.stdout+r.stderr
    audit=tmp_path/'audit.json'
    r=engine('audit',root,'--mode',scenario['mode'],'--code',home/'Code','--json',audit)
    assert r.returncode==0,r.stdout+r.stderr
    assert json.loads(audit.read_text(encoding='utf-8-sig'))['pass']
    assert not list(desktop.iterdir()) and not list(docs.iterdir())
    assert (home/'Code/app/.git/HEAD').read_text()=='ref: refs/heads/main'
    assert (root/'01_Library/raw_human/captured article.txt').read_text()=='captured knowledge'
    assert (root/'00_Inbox/_duplicates/extra article.txt').read_text()=='captured knowledge'
    if scenario.get('resume'):
        assert log.read_bytes().startswith(before)
        assert (root/'00_Inbox/_migration/undo_01_completed.json').read_bytes()==undo_before
