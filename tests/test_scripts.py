import json
from pathlib import Path
import shutil
import pytest
from conftest import put, tree


def manifest(tmp, rows, bundle='01_test'):
    return put(tmp / (bundle+'.json'), json.dumps({'bundle':bundle,'description':'Approved synthetic files','moves':rows}))


def test_scan_inventory(engine, tmp_path):
    source=tmp_path/'home/Desktop'
    put(source/'a/MKT_4310 notes.txt','same')
    put(source/'b/MKT_4310 notes.txt','same')
    put(source/'c/MKT_4310 notes.txt','else')
    put(source/'app/.git/HEAD','ref: refs/heads/main')
    put(source/'app/secret.txt','repo content must not be scanned')
    out=tmp_path/'scan.json'
    result=engine('scan',source,'--out',out)
    assert result.returncode==0,result.stdout+result.stderr
    data=json.loads(out.read_text(encoding='utf-8-sig'))
    assert data['total_files']==3
    assert len(data['git_repos'])==1
    assert len(data['likely_duplicates'])==1
    assert data['name_clashes'][0]['count']==3
    assert data['spaces_in_names']['count']==3
    assert dict(data['course_codes'])['MKT_4310']>=3
    assert (source/'a/MKT_4310 notes.txt').read_text()=='same'


def test_scan_full_hash_and_empty_files(engine,tmp_path):
    source=tmp_path/'home/Desktop'
    put(source/'a.bin','x'*(4*1024*1024)+'A')
    put(source/'b.bin','x'*(4*1024*1024)+'B')
    put(source/'empty1','');put(source/'empty2','')
    out=tmp_path/'scan.json'
    r=engine('scan',source,'--out',out)
    assert r.returncode==0,r.stdout+r.stderr
    d=json.loads(out.read_text(encoding='utf-8-sig'))
    assert len(d['likely_duplicates'])==1
    assert d['likely_duplicates'][0]['size']==0


@pytest.mark.parametrize('same',[False,True])
def test_existing_destination_refused(engine,tmp_path,same):
    root=tmp_path/'home/OneDrive/Cowork'
    s=put(tmp_path/'home/Desktop/notes.txt','one')
    d=put(root/'00_Inbox/to_sort/notes.txt','one' if same else 'two')
    m=manifest(tmp_path,[{'src':str(s),'dst':str(d)}])
    for extra in [('--dry-run',),()]:
        r=engine('move_bundle',m,'--cowork',root,*extra)
        assert r.returncode==1,r.stdout+r.stderr
        assert ('duplicate' if same else 'clash') in r.stdout
    assert s.read_text()=='one'
    assert d.read_text()==('one' if same else 'two')
    assert not (root/'00_Inbox/_migration').exists()


@pytest.mark.parametrize('same',[False,True])
def test_bundle_collision(engine,tmp_path,same):
    s=put(tmp_path/'home/Desktop/a','a'); t=put(tmp_path/'home/Desktop/b','a' if same else 'b')
    root=tmp_path/'home/OneDrive/Cowork'
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/a'},{'src':str(t),'dst':'00_Inbox/to_sort/a'}])
    r=engine('move_bundle',m,'--cowork',root,'--dry-run')
    assert r.returncode==1
    assert ('duplicate_in_bundle' if same else 'clash_in_bundle') in r.stdout


def test_real_move_undo_and_bundle_reuse(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork'
    s=put(tmp_path/'home/Desktop/space name.txt','original')
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/space name.txt'}])
    r=engine('move_bundle',m,'--cowork',root,'--dry-run'); assert r.returncode==0,r.stdout+r.stderr
    assert s.exists() and not root.exists()
    r=engine('move_bundle',m,'--cowork',root); assert r.returncode==0,r.stdout+r.stderr
    d=root/'00_Inbox/to_sort/space name.txt'
    assert not s.exists() and d.read_text()=='original'
    undo=root/'00_Inbox/_migration/undo_01_test.json'; original=undo.read_bytes()
    log=root/'00_Inbox/_migration/migration_log.md'
    assert 'MOVED' in log.read_text(encoding='utf-8-sig')
    r=engine('move_bundle','--undo',undo,'--dry-run');assert r.returncode==0,r.stdout+r.stderr
    assert d.exists() and not s.exists()
    r=engine('move_bundle','--undo',undo);assert r.returncode==0,r.stdout+r.stderr
    assert s.read_text()=='original' and not d.exists()
    r=engine('move_bundle',m,'--cowork',root);assert r.returncode==1
    assert 'bundle_already_used' in r.stdout and undo.read_bytes()==original


def test_undo_refuses_occupied_source(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork';s=put(tmp_path/'home/Desktop/a','a')
    m=manifest(tmp_path,[{'src':str(s),'dst':'00_Inbox/to_sort/a'}])
    r=engine('move_bundle',m,'--cowork',root);assert r.returncode==0,r.stdout+r.stderr
    put(s,'new occupant')
    r=engine('move_bundle','--undo',root/'00_Inbox/_migration/undo_01_test.json');assert r.returncode==1
    assert s.read_text()=='new occupant' and (root/'00_Inbox/to_sort/a').read_text()=='a'


@pytest.mark.parametrize('case',['missing','directory6','file7','directory_contents','escape','overlap','parent_file','bundle_id'])
def test_unsafe_move_refused(engine,tmp_path,case):
    root=tmp_path/'home/OneDrive/Cowork';s=put(tmp_path/'home/Desktop/a','a'); dst='00_Inbox/to_sort/a';bundle='01_test'
    if case=='missing':s=tmp_path/'home/Desktop/missing'
    if case=='directory6': s=tmp_path/'home/Desktop/dir';s.mkdir();dst='00_Inbox/a/b/c/d/e'
    if case=='file7':dst='00_Inbox/a/b/c/d/e/f'
    if case=='directory_contents':s=tmp_path/'home/Desktop/dir';put(s/'a/b/c/d/e/f','f');dst='00_Inbox/dir'
    if case=='escape':dst='../escape'
    if case=='overlap':dst=str(s/'child')
    if case=='parent_file':put(root/'00_Inbox/to_sort','file');dst='00_Inbox/to_sort/a'
    if case=='bundle_id':bundle='../outside'
    m=manifest(tmp_path,[{'src':str(s),'dst':dst}])
    if case=='bundle_id':m.write_text(json.dumps({'bundle':bundle,'moves':[{'src':str(s),'dst':dst}]}))
    r=engine('move_bundle',m,'--cowork',root)
    assert r.returncode==1,r.stdout+r.stderr
    assert s.exists() or case=='missing'


@pytest.mark.parametrize('mode',['professional','student'])
def test_audit_correct_tree_and_advisory_names(engine,tmp_path,mode):
    root=tree(tmp_path/'home',mode)
    put(root/'00_Inbox/to_sort/my final copy.txt')
    out=tmp_path/'audit.json'
    r=engine('audit',root,'--mode',mode,'--code',tmp_path/'home/Code','--json',out)
    assert r.returncode==0,r.stdout+r.stderr
    data=json.loads(out.read_text(encoding='utf-8-sig'))
    assert data['pass'] and data['suggestions']


@pytest.mark.parametrize('problem',[
    'root','frontdoor','inbox','library','raw_human','raw_AI','library_route','wiki','wiki_index','agent_route','agent_claude','agent_projects','agent_resources','context','archive','client_claude','client_projects','client_resources','stage','unnumbered','range','length','depth','git','code','student30','class_archive','course_resources'
])
def test_audit_structure_failures(engine,tmp_path,problem):
    mode='student' if problem in ['student30','class_archive','course_resources'] else 'professional'
    root=tree(tmp_path/'home',mode)
    target={
      'root':'.claude/CLAUDE.md','frontdoor':'start_here.md','inbox':'00_Inbox','library':'01_Library',
      'raw_human':'01_Library/raw_human','raw_AI':'01_Library/raw_AI','library_route':'01_Library/CLAUDE.md',
      'wiki':'01_Library/10_Email_Wiki','wiki_index':'01_Library/10_Email_Wiki/index.md','agent_claude':'10_Email/.claude/CLAUDE.md',
      'agent_projects':'10_Email/Projects','agent_resources':'10_Email/Resources','context':'10_Email/Resources/context.md','archive':'10_Email/Archive',
      'client_claude':'21_Acme/.claude/CLAUDE.md','client_projects':'21_Acme/Projects','client_resources':'21_Acme/Resources',
      'stage':'21_Acme/Projects/2026_Q4_Launch/01_brief','class_archive':'10_Class/Archive/job_search','course_resources':'10_Class/MKT_4310_Research/Resources'
    }.get(problem)
    if target:
        p=root/target
        if p.is_dir():shutil.rmtree(p)
        else:p.unlink()
    if problem=='agent_route':put(root/'.claude/CLAUDE.md','No routing')
    if problem in ['unnumbered','range','student30']:(root/{'unnumbered':'Stuff','range':'40_Extra','student30':'30_Health'}[problem]).mkdir()
    if problem=='length':put(root/'10_Email/.claude/CLAUDE.md','line\n'*200)
    if problem=='depth':(root/'00_Inbox/a/b/c/d/e').mkdir(parents=True)
    if problem=='git':put(root/'00_Inbox/app/.git/HEAD','fake')
    code=tmp_path/'home/Code'
    if problem=='code':code=tmp_path/'home/OneDrive/Code';code.mkdir()
    r=engine('audit',root,'--mode',mode,'--code',code)
    assert r.returncode!=0,r.stdout+r.stderr
