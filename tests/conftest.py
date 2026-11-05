import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skill/ai-office-builder/scripts'


@pytest.fixture(params=['python', 'powershell'])
def engine(request):
    if request.param == 'powershell' and os.name != 'nt':
        pytest.skip('Windows fallback is tested on Windows')
    shell = shutil.which(os.environ.get('OFFICE_TEST_POWERSHELL', 'pwsh')) or shutil.which('powershell')
    if request.param == 'powershell' and not shell:
        pytest.skip('PowerShell not installed')
    def run(script, *args):
        if request.param == 'python':
            cmd = [sys.executable, '-X', 'utf8', str(SCRIPTS / (script + '.py'))]
        else:
            cmd = [shell, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPTS / (script + '.ps1'))]
            # PowerShell uses named parameters with one leading dash.
            args = tuple('-' + x[2:] if isinstance(x, str) and x.startswith('--') else x for x in args)
        return subprocess.run(cmd + [str(a) for a in args], capture_output=True, text=True, encoding='utf-8', env={**os.environ, 'PYTHONUTF8':'1'}, timeout=60)
    run.name = request.param
    return run


def put(path, text='Synthetic workshop fixture.\n'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def tree(home, mode='professional'):
    root = home / 'OneDrive/Cowork'
    agents = ['10_Class', '11_Calendar', '12_Money', '13_Fitness', '14_Career'] if mode == 'student' else ['10_Email','11_Writing','12_Analytics','13_Calendar']
    put(root / 'start_here.md', '# Your AI office\nMarketing student.' if mode == 'student' else '# Your AI office\nIndependent marketing professional.')
    put(root / '.claude/CLAUDE.md', '# Floor plan\n' + '\n'.join(agents))
    for d in ['00_Inbox/to_sort','00_Inbox/_duplicates','00_Inbox/_migration','01_Library/raw_human','01_Library/raw_AI']:
        (root / d).mkdir(parents=True, exist_ok=True)
    put(root / '01_Library/CLAUDE.md', '# Library\n' + '\n'.join(a+'_Wiki' for a in agents))
    for agent in agents:
        put(root / agent / '.claude/CLAUDE.md', '# '+agent+'\nDraft work for review; never send without approval.\n')
        put(root / agent / 'Resources/context.md', '# Now\nWorkshop setup.\n# Done\n# Next\n# Decisions\nKeep original names.\n')
        for d in ['Projects','Archive']:
            (root / agent / d).mkdir(parents=True, exist_ok=True)
        put(root / '01_Library' / (agent+'_Wiki') / 'index.md', '---\ntitle: '+agent+' wiki\ntags: [index]\n---\nGeneral knowledge only.\n')
    clients = ['21_Campus_Design'] if mode == 'student' else ['21_Acme','22_Birch']
    for client in clients:
        put(root / client / '.claude/CLAUDE.md', '# '+client+'\nClient work stays here. Drafts in 03_build, deliveries in 04_output.\n')
        (root / client / 'Resources').mkdir(parents=True)
        for stage in ['01_brief','02_spec','03_build','04_output']:
            (root / client / 'Projects/2026_Q4_Launch' / stage).mkdir(parents=True)
    if mode == 'student':
        for d in ['major_classes','gened_classes','job_search']:
            (root / '10_Class/Archive' / d).mkdir(parents=True)
        for course in ['MKT_4310_Research','ACCT_2100_Accounting','ENGL_1030_Composition','STAT_2300_Statistics','PSYC_2010_Psychology']:
            put(root / '10_Class' / course / 'Resources/context.md', '# Now\nCurrent course.\n# Done\n# Next\n# Decisions\nKeep full documents.\n')
            (root / '10_Class' / course / 'Projects').mkdir(parents=True)
    else:
        for d in ['Projects','Resources']:
            (root / '30_Health' / d).mkdir(parents=True)
    (home / 'Code').mkdir(parents=True, exist_ok=True)
    return root
