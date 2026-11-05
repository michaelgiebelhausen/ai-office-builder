import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from types import SimpleNamespace
import pytest
from conftest import SCRIPTS, put
from test_scripts import manifest


def ps(command):
    shell=shutil.which('powershell') or shutil.which('pwsh')
    return subprocess.run([shell,'-NoProfile','-EncodedCommand',base64.b64encode(command.encode('utf-16-le')).decode()],capture_output=True,text=True,timeout=30)


def quoted(path):
    return "'"+str(path).replace("'","''")+"'"


@contextmanager
def directory_link(link,target):
    if os.name=='nt':
        result=ps('New-Item -ItemType Junction -Path '+quoted(link)+' -Target '+quoted(target)+' | Out-Null')
        assert result.returncode==0,result.stderr
    else:
        link.symlink_to(target,target_is_directory=True)
    try:
        yield
    finally:
        if os.name=='nt':
            result=ps('[IO.Directory]::Delete('+quoted(link)+')')
            assert result.returncode==0,result.stderr
        else:
            link.unlink()


@pytest.mark.parametrize('tag,attributes,mode,expected',[
    (0xA0000003,0x400,stat.S_IFDIR,True),
    (0xA000000C,0x400,stat.S_IFLNK,True),
    (0x9000001A,0x400,stat.S_IFREG,False),
    (0,0x400,stat.S_IFDIR,True),
])
def test_python310_reparse_guard_without_new_pathlib_api(tmp_path,monkeypatch,tag,attributes,mode,expected):
    sys.path.insert(0,str(SCRIPTS))
    from path_safety import linked
    junction=tmp_path/'redirect';child=junction/'outside.txt'
    def info(path):
        if path==child and expected:raise AssertionError('Inspected a child below a redirected ancestor')
        if path==junction:return SimpleNamespace(st_mode=mode,st_file_attributes=attributes,st_reparse_tag=tag)
        return SimpleNamespace(st_mode=stat.S_IFDIR,st_file_attributes=0,st_reparse_tag=0)
    def unsupported(*args):raise AssertionError('New pathlib API used')
    monkeypatch.setattr(Path,'lstat',info)
    monkeypatch.setattr(Path,'is_junction',unsupported,raising=False)
    assert linked(child)==expected


def test_scan_and_preview_do_not_follow_directory_redirection(engine,tmp_path):
    home=tmp_path/'home';desktop=home/'Desktop';desktop.mkdir(parents=True)
    outside=home/'Outside';put(outside/'outside-only.txt','synthetic outside scope')
    with directory_link(desktop/'redirect',outside):
        out=tmp_path/'scan.json';r=engine('scan',desktop,'--out',out);assert r.returncode==0,r.stdout+r.stderr
        assert json.loads(out.read_text(encoding='utf-8-sig'))['total_files']==0
        source=put(desktop/'normal.txt','normal')
        m=manifest(tmp_path,[{'src':str(source),'dst':'00_Inbox/to_sort/normal.txt'}])
        r=engine('move_bundle',m,'--cowork',home/'OneDrive/Cowork','--dry-run');assert r.returncode==0,r.stdout+r.stderr
        preview=json.loads(Path(str(m)+'.preview.json').read_text(encoding='utf-8-sig'))
        assert all('outside-only' not in p for p in preview['dependencies']['files'])


@pytest.mark.parametrize('changed',[False,True])
def test_successful_retry_reconciles_only_matching_fingerprints(engine,tmp_path,changed):
    home=tmp_path/'home';root=home/'OneDrive/Cowork';desktop=home/'Desktop'
    a=put(desktop/'a.txt','a');b=put(desktop/'b.txt','b')
    first=manifest(tmp_path,[{'src':str(a),'dst':'00_Inbox/to_sort/a.txt'},{'src':str(b),'dst':'00_Inbox/to_sort/b.txt'}],'first')
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',first,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    (root/'00_Inbox/to_sort/b.txt').rename(b)
    log=root/'00_Inbox/_migration/migration_log.md'
    lines=log.read_text(encoding='utf-8-sig').splitlines()
    lines=[line for line in lines if not (line.startswith('VERIFIED ') and json.loads(line[9:])['src']==str(b))]
    put(log,'\n'.join(lines)+'\n')
    if changed:put(b,'newly edited b')
    retry=manifest(tmp_path,[{'src':str(b),'dst':'00_Inbox/to_sort/b.txt'}],'retry')
    for args in [('--dry-run',),()]:
        r=engine('move_bundle',retry,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    settings=put(tmp_path/'choices.json',json.dumps({'mode':'student','renaming':'none','reference_roots':[str(desktop)],'pending_bundles':['first','retry']}))
    r=engine('move_bundle','--cowork',root,'--save-session',settings);assert r.returncode==0,r.stdout+r.stderr
    r=engine('move_bundle','--cowork',root,'--resume');data=json.loads(r.stdout)
    assert r.returncode==(1 if changed else 0),r.stdout+r.stderr
    if changed:assert data['blocked']==['first']
    else:
        assert data['pending']==[] and data['blocked']==[]
        original=next(x for x in data['bundles'] if x['bundle']=='first')
        assert 'retry' in original['verified_by']


def test_unsafe_changed_tree_blocks_only_affected_bundle(engine,tmp_path):
    home=tmp_path/'home';root=home/'OneDrive/Cowork';desktop=home/'Desktop';folder=desktop/'folder'
    put(folder/'a.txt','a');good=put(desktop/'good.txt','good')
    for bundle,source,destination in [('bad',folder,'00_Inbox/to_sort/folder'),('good',good,'00_Inbox/to_sort/good.txt')]:
        m=manifest(tmp_path,[{'src':str(source),'dst':destination}],bundle)
        for args in [('--dry-run',),()]:
            r=engine('move_bundle',m,'--cowork',root,*args);assert r.returncode==0,r.stdout+r.stderr
    settings=put(tmp_path/'choices.json',json.dumps({'mode':'student','renaming':'none','reference_roots':[str(desktop)],'pending_bundles':['bad','good']}))
    r=engine('move_bundle','--cowork',root,'--save-session',settings);assert r.returncode==0,r.stdout+r.stderr
    outside=home/'Outside';put(outside/'untouched.txt','synthetic')
    with directory_link(root/'00_Inbox/to_sort/folder/redirect',outside):
        r=engine('move_bundle','--cowork',root,'--resume');data=json.loads(r.stdout)
        assert r.returncode==1 and data['blocked']==['bad'] and data['pending']==['bad']
        assert next(x for x in data['bundles'] if x['bundle']=='good')['moved']==1
