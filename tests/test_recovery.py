import importlib.util
import json
from pathlib import Path
import sys
import pytest
from conftest import SCRIPTS, put
from test_scripts import manifest


def test_partial_failure_retains_recovery_plan(tmp_path, monkeypatch):
    sys.path.insert(0,str(SCRIPTS))
    spec=importlib.util.spec_from_file_location('migration_under_test',SCRIPTS/'move_bundle.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    root=tmp_path/'home/OneDrive/Cowork'
    a=put(tmp_path/'home/Desktop/a','a'); b=put(tmp_path/'home/Desktop/b','b')
    m={'bundle':'partial','moves':[{'src':str(a),'dst':'00_Inbox/to_sort/a'},{'src':str(b),'dst':'00_Inbox/to_sort/b'}]}
    assert not mod.check(m,root)
    original=mod.move
    def fail_second(s,d):
        if Path(s)==b:raise OSError('simulated interruption')
        original(s,d)
    monkeypatch.setattr(mod,'move',fail_second)
    with pytest.raises(OSError):mod.run(m,root)
    undo=root/'00_Inbox/_migration/undo_partial.json'
    assert undo.exists() and len(json.loads(undo.read_text())['moves'])==2
    assert not a.exists() and b.exists()
    log=(root/'00_Inbox/_migration/migration_log.md').read_text()
    assert 'MOVED' in log and str(a) in log and str(b) in log
    monkeypatch.setattr(mod,'move',original)
    assert mod.undo_bundle(undo)==0
    assert a.read_text()=='a' and b.read_text()=='b'


def test_atomic_destination_race_never_overwrites(tmp_path):
    sys.path.insert(0,str(SCRIPTS))
    from safe_move import move
    a=put(tmp_path/'a','original'); b=put(tmp_path/'b','existing')
    with pytest.raises(OSError):move(str(a),str(b))
    assert a.read_text()=='original' and b.read_text()=='existing'
    source=tmp_path/'source';source.mkdir()
    dest=tmp_path/'dest';dest.mkdir()
    with pytest.raises(OSError):move(str(source),str(dest))
    assert source.exists() and dest.exists()


def test_metadata_cannot_be_moved(engine,tmp_path):
    root=tmp_path/'home/OneDrive/Cowork'
    log=put(root/'00_Inbox/_migration/migration_log.md','Prior history')
    m=manifest(tmp_path,[{'src':str(root/'00_Inbox'),'dst':str(tmp_path/'home/Desktop/Inbox')}])
    r=engine('move_bundle',m,'--cowork',root)
    assert r.returncode==1 and 'reserved_metadata' in r.stdout
    assert log.read_text()=='Prior history'


def test_scan_cap_is_global(engine,tmp_path):
    a=tmp_path/'home/Desktop';b=tmp_path/'home/Documents'
    put(a/'one');put(a/'two');put(b/'three')
    out=tmp_path/'scan.json'
    r=engine('scan',a,b,'--out',out,'--max-files','1')
    assert r.returncode==0,r.stdout+r.stderr
    d=json.loads(out.read_text(encoding='utf-8-sig'))
    assert d['total_files']==1 and d['truncated']


def test_output_never_overwritten(engine,tmp_path):
    source=tmp_path/'home/Desktop';put(source/'one')
    out=put(tmp_path/'existing.json','KEEP')
    r=engine('scan',source,'--out',out)
    assert r.returncode!=0 and out.read_text()=='KEEP'


def test_links_not_migrated_or_scanned(engine,tmp_path):
    home=tmp_path/'home';source=home/'Desktop';source.mkdir(parents=True)
    target=put(home/'other/secret.txt','must stay here')
    try:(source/'link.txt').symlink_to(target)
    except OSError:pytest.skip('Creating symlinks requires OS permission')
    out=tmp_path/'scan.json'
    r=engine('scan',source,'--out',out);assert r.returncode==0,r.stdout+r.stderr
    assert json.loads(out.read_text(encoding='utf-8-sig'))['total_files']==0
    m=manifest(tmp_path,[{'src':str(source/'link.txt'),'dst':'00_Inbox/to_sort/link.txt'}])
    r=engine('move_bundle',m,'--cowork',home/'OneDrive/Cowork')
    assert r.returncode==1 and target.read_text()=='must stay here'
