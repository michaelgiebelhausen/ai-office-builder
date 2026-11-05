import importlib.util
import json
from pathlib import Path
import sys
import pytest
import base64
import os
import shutil
import subprocess
from conftest import SCRIPTS, put
from test_scripts import manifest


def load_mover():
    sys.path.insert(0, str(SCRIPTS))
    spec=importlib.util.spec_from_file_location('mover_safeguard_test', SCRIPTS/'move_bundle.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def test_execution_requires_preview(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork';s=put(tmp_path/'home/Desktop/a.txt','original')
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/a.txt'}])
    r=engine('move_bundle',m,'--cowork',root)
    assert r.returncode==1 and 'approval_required' in r.stdout+r.stderr
    assert s.exists() and not root.exists()


@pytest.mark.parametrize('changed',['source','manifest','incoming_consumer','new_directory_file'])
def test_changed_preview_refused(engine,tmp_path,changed):
    root=tmp_path/'home/OneDrive/Cowork';desktop=tmp_path/'home/Desktop'
    if changed=='new_directory_file':
        source=desktop/'folder';put(source/'a.txt','original')
    else:source=put(desktop/'a.txt','original')
    consumer=put(desktop/'consumer.txt','unrelated initial text')
    m=manifest(tmp_path,[{'src':str(source),'dst':'00_Inbox/to_sort/'+source.name}])
    r=engine('move_bundle',m,'--cowork',root,'--dry-run');assert r.returncode==0,r.stdout+r.stderr
    receipt=Path(str(m)+'.preview.json');before=receipt.read_bytes()
    if changed=='source':put(source,'changed after approval')
    if changed=='manifest':
        d=json.loads(m.read_text());d['moves'][0]['dst']='00_Inbox/to_sort/other.txt';m.write_text(json.dumps(d))
    if changed=='incoming_consumer':put(consumer,'new dependency '+f'[file]({source.name})')
    if changed=='new_directory_file':put(source/'new.txt','unapproved content')
    r=engine('move_bundle',m,'--cowork',root)
    assert r.returncode==1,r.stdout+r.stderr
    assert any(x in r.stdout+r.stderr for x in ['approval_changed','dependency_break'])
    assert source.exists() and not root.exists() and receipt.read_bytes()==before


@pytest.mark.parametrize('kind',['incoming','outgoing','import','html','html_query','external_config'])
def test_broken_dependency_held(engine,tmp_path,kind):
    home=tmp_path/'home';desktop=home/'Desktop';root=home/'OneDrive/Cowork'
    target=put(desktop/'reading.txt','original')
    if kind=='incoming':source=target;put(desktop/'syllabus.md','[Reading](reading.txt)')
    if kind=='outgoing':source=put(desktop/'syllabus.md','[Reading](reading.txt)')
    if kind=='import':source=target;put(desktop/'.claude/CLAUDE.md','@../reading.txt.md');target.rename(desktop/'reading.txt.md');source=desktop/'reading.txt.md'
    if kind=='html':source=target;put(desktop/'page.html','<a href="reading.txt">Read</a>')
    if kind=='html_query':source=target;put(desktop/'page.html','<script src="./reading.txt?v=1#load"></script>')
    if kind=='external_config':source=target;put(home/'config/job.json',json.dumps({'input':str(source)}))
    m=manifest(tmp_path,[{'src':str(source),'dst':'00_Inbox/to_sort/'+source.name}])
    if kind=='external_config':
        data=json.loads(m.read_text());data['reference_roots'].append(str(home/'config'));m.write_text(json.dumps(data))
    r=engine('move_bundle',m,'--cowork',root,'--dry-run')
    assert r.returncode==1 and 'dependency_break' in r.stdout+r.stderr,r.stdout+r.stderr
    assert source.exists() and not root.exists() and not Path(str(m)+'.preview.json').exists()


@pytest.mark.parametrize('trailing',[False,True])
def test_related_folder_preserves_links_and_verifies(engine,tmp_path,trailing):
    home=tmp_path/'home';root=home/'OneDrive/Cowork';source=home/'Desktop/course'
    put(source/'syllabus.md','[Reading](reading.txt)\n[Web](https://example.com)')
    put(source/'reading.txt','full-text reading')
    put(source/'page.html','<script src="./reading.txt?v=1#load"></script>')
    m=manifest(tmp_path,[{'src':str(source)+(os.sep if trailing else ''),'dst':'10_Class/Projects/course'}])
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',m,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    assert not source.exists() and (root/'10_Class/Projects/course/reading.txt').read_text()=='full-text reading'
    assert 'VERIFIED' in (root/'00_Inbox/_migration/migration_log.md').read_text(encoding='utf-8-sig')
    r=engine('move_bundle','--undo',root/'00_Inbox/_migration/undo_01_test.json');assert r.returncode==0,r.stdout+r.stderr
    assert (source/'reading.txt').read_text()=='full-text reading'


def test_multi_file_bundle_defers_links_until_target_arrives(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork';desktop=tmp_path/'home/Desktop'
    a=put(desktop/'a.md','[Read](b.txt)');b=put(desktop/'b.txt','b')
    m=manifest(tmp_path,[{'src':str(a),'dst':'00_Inbox/to_sort/a.md'},{'src':str(b),'dst':'00_Inbox/to_sort/b.txt'}])
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',m,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    assert (root/'00_Inbox/to_sort/a.md').exists() and (root/'00_Inbox/to_sort/b.txt').exists()


def test_undo_refuses_modified_directory(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork';source=tmp_path/'home/Desktop/folder'
    put(source/'a.txt','a')
    m=manifest(tmp_path,[{'src':str(source),'dst':'00_Inbox/to_sort/folder'}])
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',m,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    put(root/'00_Inbox/to_sort/folder/a.txt','modified')
    r=engine('move_bundle','--undo',root/'00_Inbox/_migration/undo_01_test.json')
    assert r.returncode==1 and not source.exists()
    assert (root/'00_Inbox/to_sort/folder/a.txt').read_text()=='modified'


def test_opaque_application_requires_recorded_review(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork';s=put(tmp_path/'home/Desktop/deck.pptx','synthetic application format')
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/deck.pptx'}]);data=json.loads(m.read_text());data.pop('dependency_review');m.write_text(json.dumps(data))
    r=engine('move_bundle',m,'--cowork',root,'--dry-run')
    assert r.returncode==1 and 'dependency_review_required' in r.stdout+r.stderr


@pytest.mark.parametrize('answer',[None,True,42])
def test_owner_review_must_be_text(engine,tmp_path,answer):
    root=tmp_path/'home/OneDrive/Cowork';s=put(tmp_path/'home/Desktop/a.txt','a')
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/a.txt'}])
    d=json.loads(m.read_text());d['dependency_review']=answer;m.write_text(json.dumps(d))
    r=engine('move_bundle',m,'--cowork',root,'--dry-run')
    assert r.returncode==1 and 'dependency_review_required' in r.stdout+r.stderr
    assert s.exists() and not root.exists()


def test_reference_roots_are_required(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork';s=put(tmp_path/'home/Desktop/a.txt')
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/a.txt'}]);data=json.loads(m.read_text());data.pop('reference_roots');m.write_text(json.dumps(data))
    r=engine('move_bundle',m,'--cowork',root,'--dry-run')
    assert r.returncode==1 and 'reference_roots' in r.stdout+r.stderr


def test_session_dry_run_does_not_write(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork'
    settings=put(tmp_path/'choices.json',json.dumps({'mode':'student','renaming':'none','pending_bundles':[]}))
    r=engine('move_bundle','--cowork',root,'--save-session',settings,'--dry-run')
    assert r.returncode==0,r.stdout+r.stderr
    assert not root.exists()


def test_resume_without_snapshot_does_not_invent_choices(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork'
    r=engine('move_bundle','--cowork',root,'--resume')
    assert r.returncode==1 and not root.exists()


def test_changed_preview_can_be_replaced_only_with_new_path(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork';s=put(tmp_path/'home/Desktop/a.txt','a')
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/a.txt'}])
    r=engine('move_bundle',m,'--cowork',root,'--dry-run');assert r.returncode==0,r.stdout+r.stderr
    old=Path(str(m)+'.preview.json');before=old.read_bytes();put(s,'approved revised contents')
    new=tmp_path/'renewed.json'
    r=engine('move_bundle',m,'--cowork',root,'--dry-run','--approval',new);assert r.returncode==0,r.stdout+r.stderr
    r=engine('move_bundle',m,'--cowork',root,'--approval',new);assert r.returncode==0,r.stdout+r.stderr
    assert old.read_bytes()==before and (root/'00_Inbox/to_sort/a.txt').read_text()=='approved revised contents'


def test_manifest_in_scan_root_is_not_treated_as_a_consumer(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork';desktop=tmp_path/'home/Desktop';s=put(desktop/'a.txt','a')
    m=manifest(desktop,[{'src':str(s),'dst':'00_Inbox/to_sort/a.txt'}])
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',m,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    assert (root/'00_Inbox/to_sort/a.txt').read_text()=='a'


def test_prior_preview_does_not_block_later_bundle(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork';desktop=tmp_path/'home/Desktop'
    a=put(desktop/'a.txt','a');b=put(desktop/'b.txt','b')
    first=manifest(desktop,[{'src':str(a),'dst':'00_Inbox/to_sort/a.txt'}],'first')
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',first,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    second=manifest(desktop,[{'src':str(b),'dst':'00_Inbox/to_sort/b.txt'}],'second')
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',second,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr


def test_non_ascii_preview_and_session_round_trip(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork';source=tmp_path/'home/Desktop/économie'
    put(source/'résumé.txt','élève')
    m=manifest(tmp_path,[{'src':str(source),'dst':'00_Inbox/to_sort/économie'}])
    data=json.loads(m.read_text());data['dependency_review']='Élève confirmed no external consumers';m.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    choices={'mode':'student','renaming':'none','name':'Zoë García','reference_roots':[str(source.parent)],'pending_bundles':['01_test']}
    settings=put(tmp_path/'choices.json',json.dumps(choices,ensure_ascii=False))
    r=engine('move_bundle','--cowork',root,'--save-session',settings);assert r.returncode==0,r.stdout+r.stderr
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',m,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    r=engine('move_bundle','--cowork',root,'--resume');assert r.returncode==0,r.stdout+r.stderr
    assert json.loads(r.stdout)['choices']==choices
    assert (root/'00_Inbox/to_sort/économie/résumé.txt').read_text(encoding='utf-8')=='élève'


@pytest.mark.parametrize('uri',[False,True,'upper'])
def test_decoded_json_unicode_dependency_held(engine,tmp_path,uri):
    home=tmp_path/'home';root=home/'OneDrive/Cowork';s=put(home/'Zoë/Desktop/reading.txt','reading')
    target=s.as_uri() if uri else str(s)
    if uri=='upper':target=target.replace('file:', 'FILE:', 1)
    put(home/'config/job.json',json.dumps({'input':target},ensure_ascii=True))
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/reading.txt'}])
    d=json.loads(m.read_text());d['reference_roots'].append(str(home/'config'));m.write_text(json.dumps(d))
    r=engine('move_bundle',m,'--cowork',root,'--dry-run')
    assert r.returncode==1 and 'dependency_break' in r.stdout+r.stderr
    assert s.exists() and not root.exists()


def test_preview_does_not_consume_its_own_scan_budget(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork';desktop=tmp_path/'home/Desktop';s=put(desktop/'a.txt','a')
    m=manifest(desktop,[{'src':str(s),'dst':'00_Inbox/to_sort/a.txt'}])
    d=json.loads(m.read_text());d['reference_limit']=2;m.write_text(json.dumps(d))
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',m,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr


def test_reference_budget_counts_unsupported_entries(engine,tmp_path):
    home=tmp_path/'home';root=home/'OneDrive/Cowork';s=put(home/'Desktop/a.bin','a')
    put(home/'Desktop/b.bin','b');put(home/'Desktop/c.bin','c')
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/a.bin'}])
    d=json.loads(m.read_text());d['reference_limit']=3;m.write_text(json.dumps(d))
    r=engine('move_bundle',m,'--cowork',root,'--dry-run')
    assert r.returncode==1 and 'reference_inspection_limit' in r.stdout+r.stderr
    assert s.exists() and not root.exists()


@pytest.mark.parametrize('corruption',['outside_scope','wrong_path_prefix','wrong_bundle'])
def test_recovery_rejects_unapproved_paths_and_inexact_log(engine,tmp_path,corruption):
    home=tmp_path/'home';root=home/'OneDrive/Cowork';s=put(home/'Desktop/a.txt','a')
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/a.txt'}])
    choices={'mode':'student','renaming':'none','reference_roots':[str(home/'Desktop')],'pending_bundles':['01_test']}
    settings=put(tmp_path/'choices.json',json.dumps(choices))
    r=engine('move_bundle','--cowork',root,'--save-session',settings);assert r.returncode==0,r.stdout+r.stderr
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',m,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    undo=root/'00_Inbox/_migration/undo_01_test.json';u=json.loads(undo.read_text(encoding='utf-8-sig'))
    event={'bundle':'01_test','src':str(s),'dst':str(root/'00_Inbox/to_sort/a.txt')}
    if corruption=='outside_scope':
        outside=put(home/'Unapproved/current.txt','a')
        original=home/'Unapproved/original.txt'
        u['moves'][0]['src']=str(outside);u['moves'][0]['dst']=str(original)
        undo.write_text(json.dumps(u),encoding='utf-8')
        event['src']=str(original);event['dst']=str(outside)
    if corruption=='wrong_path_prefix':event['src']+='.bak';event['dst']+='.bak'
    if corruption=='wrong_bundle':event['bundle']='unrelated_bundle'
    put(root/'00_Inbox/_migration/migration_log.md','VERIFIED '+json.dumps(event)+'\n')
    r=engine('move_bundle','--cowork',root,'--resume')
    assert r.returncode==1,r.stdout+r.stderr
    d=json.loads(r.stdout);assert d['blocked']==['01_test'] and d['pending']==['01_test']


@pytest.mark.parametrize('authorize_code',[False,True])
def test_resume_code_destination_requires_saved_scope(engine,tmp_path,authorize_code):
    home=tmp_path/'home';root=home/'OneDrive/Cowork';source=home/'Desktop/app'
    put(source/'.git/HEAD','ref: refs/heads/main');put(source/'main.txt','synthetic repo')
    (home/'Code').mkdir()
    m=manifest(tmp_path,[{'src':str(source),'dst':str(home/'Code/app')}])
    choices={'mode':'student','renaming':'none','reference_roots':[str(home/'Desktop')],'pending_bundles':['01_test']}
    if authorize_code:choices['destination_roots']=[str(home/'Code')]
    settings=put(tmp_path/'choices.json',json.dumps(choices))
    r=engine('move_bundle','--cowork',root,'--save-session',settings);assert r.returncode==0,r.stdout+r.stderr
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',m,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    r=engine('move_bundle','--cowork',root,'--resume');data=json.loads(r.stdout)
    assert r.returncode==(0 if authorize_code else 1),r.stdout+r.stderr
    assert data['pending']==([] if authorize_code else ['01_test'])


def test_undone_bundle_returns_to_pending_after_completed_checkpoint(engine,tmp_path):
    home=tmp_path/'home';root=home/'OneDrive/Cowork';s=put(home/'Desktop/a.txt','a')
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/a.txt'}])
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',m,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    settings=put(tmp_path/'choices.json',json.dumps({'mode':'student','renaming':'none','reference_roots':[str(home/'Desktop')],'pending_bundles':[]}))
    r=engine('move_bundle','--cowork',root,'--save-session',settings);assert r.returncode==0,r.stdout+r.stderr
    r=engine('move_bundle','--undo',root/'00_Inbox/_migration/undo_01_test.json');assert r.returncode==0,r.stdout+r.stderr
    r=engine('move_bundle','--cowork',root,'--resume');assert r.returncode==0,r.stdout+r.stderr
    assert json.loads(r.stdout)['pending']==['01_test']


def test_private_path_rejected_without_access(tmp_path,monkeypatch):
    load_mover()
    from safeguards import inventory
    def forbidden(*args,**kwargs):raise AssertionError('No filesystem inspection should occur')
    monkeypatch.setattr(Path,'is_symlink',forbidden)
    monkeypatch.setattr(Path,'is_file',forbidden)
    monkeypatch.setattr(Path,'is_dir',forbidden)
    with pytest.raises(ValueError,match='private_path_in_bundle'):
        inventory(tmp_path/'99_Private/a.txt')


@pytest.mark.parametrize('side',['source','destination'])
def test_cli_private_paths_held_without_creating_them(engine,tmp_path,side):
    root=tmp_path/'home/OneDrive/Cowork'
    source=put(tmp_path/'home/Desktop/a.txt','a')
    if side=='source':source=tmp_path/'home/Desktop/99_Private/missing.txt'
    dst='00_Inbox/99_Private/a.txt' if side=='destination' else '00_Inbox/to_sort/a.txt'
    m=manifest(tmp_path,[{'src':str(source),'dst':dst}])
    r=engine('move_bundle',m,'--cowork',root,'--dry-run')
    assert r.returncode==1 and 'private_path_in_bundle' in r.stdout+r.stderr
    assert not root.exists()



@pytest.mark.parametrize('state',['finished','edited_destination','occupied_original','partial','undone','missing_log'])
def test_session_reconciliation(engine,tmp_path,state):
    home=tmp_path/'home';root=home/'OneDrive/Cowork';desktop=home/'Desktop'
    a=put(desktop/'a.txt','a');b=put(desktop/'b.txt','b')
    m=manifest(tmp_path,[{'src':str(a),'dst':'00_Inbox/to_sort/a.txt'},{'src':str(b),'dst':'00_Inbox/to_sort/b.txt'}])
    choices={'mode':'student','renaming':'none','courses':['MKT_4310'],'reference_roots':[str(desktop)],'pending_bundles':['01_test','02_later']}
    settings=put(tmp_path/'choices.json',json.dumps(choices))
    r=engine('move_bundle','--cowork',root,'--save-session',settings);assert r.returncode==0,r.stdout+r.stderr
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',m,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    if state=='edited_destination':put(root/'00_Inbox/to_sort/a.txt','edited')
    if state=='occupied_original':put(a,'different file')
    if state=='partial':(root/'00_Inbox/to_sort/b.txt').rename(b)
    if state=='missing_log':(root/'00_Inbox/_migration/migration_log.md').unlink()
    if state=='undone':
        r=engine('move_bundle','--undo',root/'00_Inbox/_migration/undo_01_test.json');assert r.returncode==0,r.stdout+r.stderr
    r=engine('move_bundle','--cowork',root,'--resume')
    data=json.loads(r.stdout)
    assert data['choices']==choices
    if state=='finished':assert r.returncode==0 and data['pending']==['02_later']
    elif state=='undone':assert r.returncode==0 and data['pending']==['01_test','02_later']
    else:assert r.returncode==1 and data['blocked']==['01_test'] and '01_test' in data['pending']


def test_verification_failure_stops_next_move(tmp_path,monkeypatch):
    mod=load_mover();root=tmp_path/'home/OneDrive/Cowork';a=put(tmp_path/'home/Desktop/a','a');b=put(tmp_path/'home/Desktop/b','b')
    m={'bundle':'verification','moves':[{'src':str(a),'dst':'00_Inbox/to_sort/a'},{'src':str(b),'dst':'00_Inbox/to_sort/b'}]}
    assert not mod.check(m,root)
    original=mod.move
    def corrupt(s,d):original(s,d);put(Path(d),'corrupted during migration')
    monkeypatch.setattr(mod,'move',corrupt)
    with pytest.raises(ValueError,match='verification_failed'):mod.run(m,root)
    assert b.exists() and not a.exists()
    assert (root/'00_Inbox/_migration/undo_verification.json').exists()
    assert 'VERIFIED' not in (root/'00_Inbox/_migration/migration_log.md').read_text()


def test_disappearing_dependency_stops_next_move(tmp_path,monkeypatch):
    mod=load_mover();root=tmp_path/'home/OneDrive/Cowork';desktop=tmp_path/'home/Desktop'
    target=put(desktop/'reading.txt','reading');a=put(desktop/'a.md','[Read]('+target.as_uri()+')');b=put(desktop/'b.txt','b')
    m={'bundle':'dependency_failure','reference_roots':[str(desktop)],'dependency_review':'No external consumers','moves':[{'src':str(a),'dst':'00_Inbox/to_sort/a.md'},{'src':str(b),'dst':'00_Inbox/to_sort/b.txt'}]}
    assert not mod.check(m,root)
    preview=mod.snapshot(m,root);m['_dependencies']=preview['dependencies']
    for row,fp in zip(m['moves'],preview['sources']):row['_fingerprint']=fp
    original=mod.move
    def disappear(s,d):original(s,d);target.unlink()
    monkeypatch.setattr(mod,'move',disappear)
    with pytest.raises(ValueError,match='dependency_verification_failed'):mod.run(m,root)
    assert b.exists() and not a.exists()
    assert (root/'00_Inbox/_migration/undo_dependency_failure.json').exists()


def test_native_disappearing_dependency_stops_next_move(engine,tmp_path):
    if engine.name!='powershell':pytest.skip('Native PowerShell fault-injection check')
    root=tmp_path/'home/OneDrive/Cowork';desktop=tmp_path/'home/Desktop';target=put(desktop/'reading.txt','reading')
    a=put(desktop/'a.md','[Read]('+target.as_uri()+')');b=put(desktop/'b.txt','b')
    m=manifest(tmp_path,[{'src':str(a),'dst':'00_Inbox/to_sort/a.md'},{'src':str(b),'dst':'00_Inbox/to_sort/b.txt'}])
    r=engine('move_bundle',m,'--cowork',root,'--dry-run');assert r.returncode==0,r.stdout+r.stderr
    def quote(p):return "'"+str(p).replace("'","''")+"'"
    script="$global:dependencyTarget="+quote(target)+"; Set-PSBreakpoint -Command VerifyMoved -Action {[IO.File]::Delete($global:dependencyTarget)} | Out-Null; & "+quote(SCRIPTS/'move_bundle.ps1')+' '+quote(m)+' -Cowork '+quote(root)
    shell=shutil.which(os.environ.get('OFFICE_TEST_POWERSHELL','pwsh')) or shutil.which('powershell')
    r=subprocess.run([shell,'-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode()],capture_output=True,text=True,encoding='utf-8',timeout=60)
    assert r.returncode==1 and 'dependency_verification_failed' in r.stdout+r.stderr,r.stdout+r.stderr
    assert b.exists() and not a.exists()
    assert (root/'00_Inbox/_migration/undo_01_test.json').exists()


def test_native_verification_failure_stops_next_move(engine,tmp_path):
    if engine.name != 'powershell':
        pytest.skip('Native PowerShell fault-injection check')
    root=tmp_path/'home/OneDrive/Cowork';a=put(tmp_path/'home/Desktop/a','a');b=put(tmp_path/'home/Desktop/b','b')
    m=manifest(tmp_path,[{'src':str(a),'dst':'00_Inbox/to_sort/a'},{'src':str(b),'dst':'00_Inbox/to_sort/b'}])
    r=engine('move_bundle',m,'--cowork',root,'--dry-run');assert r.returncode==0,r.stdout+r.stderr
    def quote(p):return "'"+str(p).replace("'","''")+"'"
    script="$global:corruptTarget="+quote(root/'00_Inbox/to_sort/a')+"; Set-PSBreakpoint -Command VerifyMoved -Action {[IO.File]::WriteAllText($global:corruptTarget,'corrupted during migration')} | Out-Null; & "+quote(SCRIPTS/'move_bundle.ps1')+' '+quote(m)+' -Cowork '+quote(root)
    shell=shutil.which(os.environ.get('OFFICE_TEST_POWERSHELL','pwsh')) or shutil.which('powershell')
    r=subprocess.run([shell,'-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode()],capture_output=True,text=True,encoding='utf-8',timeout=60)
    assert r.returncode==1 and 'verification_failed' in r.stdout+r.stderr,r.stdout+r.stderr
    assert b.exists() and not a.exists()
    assert (root/'00_Inbox/_migration/undo_01_test.json').exists()
    assert 'VERIFIED' not in (root/'00_Inbox/_migration/migration_log.md').read_text(encoding='utf-8-sig')
