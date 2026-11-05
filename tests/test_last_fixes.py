import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from conftest import SCRIPTS, put


def test_scan_holds_inaccessible_metadata(tmp_path,monkeypatch):
    sys.path.insert(0,str(SCRIPTS))
    spec=importlib.util.spec_from_file_location('scan_inspection_test',SCRIPTS/'scan.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    folder=tmp_path/'home/Desktop';bad=put(folder/'blocked.txt','blocked');put(folder/'normal.txt','normal')
    original=mod.linked
    def deny(p):
        if Path(p)==bad:raise PermissionError('Synthetic ACL denial')
        return original(p)
    monkeypatch.setattr(mod,'linked',deny)
    out=tmp_path/'scan.json';monkeypatch.setattr(sys,'argv',['scan.py',str(folder),'--out',str(out)])
    mod.main();data=json.loads(out.read_text())
    assert data['total_files']==1 and data['inspection_errors'][0]['path']==str(bad)


def test_retry_provenance_is_case_sensitive(engine,tmp_path):
    home=tmp_path/'home';root=home/'OneDrive/Cowork';desktop=home/'Desktop';desktop.mkdir(parents=True)
    current=put(root/'00_Inbox/to_sort/current.txt','data')
    fp=[{'path':'.','kind':'file','sha256':hashlib.sha256(b'data').hexdigest()}]
    for bundle,name in [('upper','A.txt'),('lower','a.txt')]:
        put(root/('00_Inbox/_migration/undo_'+bundle+'.json'),json.dumps({'bundle':bundle,'cowork':str(root),'moves':[{'src':str(current),'dst':str(desktop/name),'fingerprint':fp}]}))
    event={'bundle':'upper','src':str(desktop/'A.txt'),'dst':str(current)}
    put(root/'00_Inbox/_migration/migration_log.md','VERIFIED '+json.dumps(event)+'\n')
    choices=put(tmp_path/'choices.json',json.dumps({'mode':'student','renaming':'none','reference_roots':[str(desktop)],'pending_bundles':['upper','lower']}))
    r=engine('move_bundle','--cowork',root,'--save-session',choices);assert r.returncode==0,r.stdout+r.stderr
    r=engine('move_bundle','--cowork',root,'--resume');data=json.loads(r.stdout)
    assert r.returncode==1 and data['blocked']==['lower'] and data['pending']==['lower']
