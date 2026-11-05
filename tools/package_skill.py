"""Build the installable ZIP, preserving exactly one skill folder at its root."""
import argparse
from pathlib import Path
import zipfile


def package(out):
    root=Path(__file__).resolve().parents[1]/'skill'
    source=root/'ai-office-builder'
    out=Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    paths=sorted(p for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            z.write(p,p.relative_to(root).as_posix())
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        assert 'ai-office-builder/SKILL.md' in z.namelist()
    print(f'Built {out} ({len(paths)} files)')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True)
    package(ap.parse_args().out)
