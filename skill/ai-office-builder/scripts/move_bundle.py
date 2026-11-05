#!/usr/bin/env python3
"""Approved moves only. Manifest: {bundle, description?, moves:[{src,dst,note?}]}.
src must be absolute; dst is absolute or relative to --cowork.
Usage: move_bundle.py manifest.json --cowork PATH [--dry-run]
       move_bundle.py --undo undo_BUNDLE.json [--dry-run]
Cross-filesystem moves are refused, without a copy/delete fallback.
An immutable undo plan is persisted BEFORE moving. Every move is logged.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from safe_move import move
from safeguards import snapshot, inventory, verify_move, verify_references, write_new, reconcile


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def same_content(a, b):
    return a.is_file() and b.is_file() and a.stat().st_size == b.stat().st_size and sha(a) == sha(b)


def identity(p):
    s = p.stat()
    return [s.st_dev, s.st_ino]


def linked(p):
    return any(x.is_symlink() or (hasattr(x, 'is_junction') and x.is_junction()) for x in (p, *p.parents))


def inside(p, parent):
    return p == parent or parent in p.parents


def existing_parent(p):
    while not p.exists():
        p = p.parent
    return p


def check(m, cowork):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', m.get('bundle', '')):
        raise ValueError('bundle must contain only letters, digits, underscores or hyphens')
    if not isinstance(m.get('moves'), list) or not m['moves']:
        raise ValueError('moves must be a nonempty list')
    problems, pairs = [], []
    for i, row in enumerate(m['moves']):
        s = Path(row['src']).expanduser()
        if not s.is_absolute():
            raise ValueError('source paths must be absolute')
        d = Path(row['dst']).expanduser()
        if not d.is_absolute():
            d = cowork / d
            if not inside(Path(os.path.abspath(d)), cowork):
                problems.append(('destination_escape', i))
        s, d = Path(os.path.abspath(s)), Path(os.path.abspath(d))
        row['_src'], row['_dst'] = str(s), str(d)
        if any(part.casefold() in ('99_private', '.obsidian') for part in (*s.parts, *d.parts)):
            problems.append(('private_path_in_bundle', i))
            continue
        if linked(s) or linked(d):
            problems.append(('linked_path', i))
            continue
        if not s.exists():
            problems.append(('missing_source', i))
        if d.exists():
            problems.append(('duplicate' if s.exists() and same_content(s, d) else 'clash', i))
        if inside(d, s) or inside(s, d):
            problems.append(('overlapping_paths', i))
        if s.exists() and s.stat().st_dev != existing_parent(d.parent).stat().st_dev:
            problems.append(('cross_filesystem', i))
        if not existing_parent(d.parent).is_dir():
            problems.append(('parent_is_file', i))
        if inside(d, cowork):
            depth = len(d.relative_to(cowork).parts)
            max_depth = 5 if s.is_dir() else 6
            if s.is_dir():
                for base, dirs, files in os.walk(s):
                    held_dirs = [n for n in dirs if linked(Path(base) / n)]
                    if held_dirs:
                        problems.append(('linked_path', i))
                        dirs[:] = [n for n in dirs if n not in held_dirs]
                    if linked(Path(base)) or any(linked(Path(base) / n) for n in dirs + files):
                        problems.append(('linked_path', i))
                    relative = len(Path(base).relative_to(s).parts)
                    if depth + relative > 5 or (files and depth + relative + 1 > 6):
                        problems.append(('too_deep', i))
                    if '.git' in dirs or '.git' in files:
                        problems.append(('git_in_cowork', i))
            if depth > max_depth:
                problems.append(('too_deep', i))
        metadata = cowork / '00_Inbox' / '_migration'
        if inside(d, metadata) or inside(s, metadata) or inside(metadata, s):
            problems.append(('reserved_metadata', i))
        for ps, pd in pairs:
            if d == pd:
                problems.append(('duplicate_in_bundle' if s.exists() and ps.exists() and same_content(s, ps) else 'clash_in_bundle', i))
            elif any((inside(d, pd), inside(pd, d), inside(s, ps), inside(ps, s), inside(d, ps), inside(ps, d), inside(s, pd), inside(pd, s))):
                problems.append(('overlapping_bundle', i))
        pairs.append((s, d))
    undo = cowork / '00_Inbox/_migration' / ('undo_' + m['bundle'] + '.json')
    if undo.exists():
        problems.append(('bundle_already_used', -1))
    if linked(undo) or linked(cowork / '00_Inbox/_migration/migration_log.md'):
        problems.append(('linked_metadata', -1))
    return problems


def append(log, text):
    with log.open('a', encoding='utf-8') as f:
        f.write(text + '\n')
        f.flush()
        os.fsync(f.fileno())


def run(m, cowork):
    folder = cowork / '00_Inbox/_migration'
    folder.mkdir(parents=True, exist_ok=True)
    undo = folder / ('undo_' + m['bundle'] + '.json')
    log = folder / 'migration_log.md'
    plan = {'bundle': m['bundle'], 'cowork': str(cowork), 'moves': [
        {'src': r['_dst'], 'dst': r['_src'], 'identity': identity(Path(r['_src'])), 'fingerprint': (r.get('_fingerprint') or inventory(r['_src']))}
        for r in reversed(m['moves'])]}
    with undo.open('x', encoding='utf-8') as f:
        json.dump(plan, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    append(log, f"\n## {datetime.datetime.now().isoformat()} bundle {m['bundle']}\n{m.get('description', '')}\nUndo: {undo}")
    if m.get('_approval_path'):
        append(log, 'Approved preview: ' + m['_approval_path'])
    done = 0
    completed = []
    fingerprints = {r['src']: r['fingerprint'] for r in plan['moves']}
    for row in m['moves']:
        s, d = Path(row['_src']), Path(row['_dst'])
        expected = fingerprints[str(d)]
        if inventory(s) != expected or linked(d):
            raise ValueError('approval_changed: source or destination parent changed during execution')
        append(log, f'INTENT `{s}` -> `{d}`')
        d.parent.mkdir(parents=True, exist_ok=True)
        move(str(s), str(d))
        done += 1
        append(log, f'MOVED `{s}` -> `{d}` {row.get("note", "")}')
        expected = fingerprints[str(d)]
        verify_move(row, expected)
        completed.append(row)
        verify_references(m.get('_dependencies', {}), completed)
        append(log, 'VERIFIED ' + json.dumps({'bundle': m['bundle'], 'src': str(s), 'dst': str(d)}))
    print(f'Moved {done} item(s). Logged. Undo file: {undo}')
    return 0


def undo_bundle(path, dry_run=False):
    u = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    log = Path(u['cowork']) / '00_Inbox/_migration/migration_log.md'
    skipped, back = 0, 0
    for row in u['moves']:
        s, d = Path(row['src']), Path(row['dst'])
        if d.exists() and not s.exists() and identity(d) == row['identity']:
            continue
        if not s.exists() or d.exists() or linked(s) or linked(d) or identity(s) != row['identity']:
            print(f'skip (missing, changed, linked or occupied): {s} -> {d}')
            skipped += 1
            continue
        if row.get('fingerprint') is not None and inventory(s) != row['fingerprint']:
            print(f'skip (changed contents): {s}')
            skipped += 1
            continue
        print(f'UNDO {s} -> {d}')
        if not dry_run:
            if linked(log):
                raise ValueError('linked metadata')
            append(log, f'UNDO INTENT `{s}` -> `{d}`')
            d.parent.mkdir(parents=True, exist_ok=True)
            move(str(s), str(d))
            append(log, f'UNDO MOVED `{s}` -> `{d}`')
        back += 1
    print(f'{"Would restore" if dry_run else "Restored"} {back} item(s); skipped {skipped}.')
    return 1 if skipped else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest', nargs='?')
    ap.add_argument('--cowork')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--undo')
    ap.add_argument('--approval', help='Saved preview path; defaults to MANIFEST.preview.json')
    ap.add_argument('--save-session', help='JSON containing interview choices and pending_bundles')
    ap.add_argument('--resume', action='store_true')
    a = ap.parse_args()
    try:
        if sum(map(bool, (a.undo, a.save_session, a.resume))) > 1:
            raise ValueError('Choose one of undo, save-session or resume')
        if a.save_session or a.resume:
            if not a.cowork:
                ap.error('--cowork is required for session operations')
            cowork = Path(os.path.abspath(Path(a.cowork).expanduser()))
            folder = cowork / '00_Inbox/_migration'
            if a.save_session:
                state = json.loads(Path(a.save_session).read_text(encoding='utf-8-sig'))
                if state.get('mode') not in ('student', 'professional') or state.get('renaming') not in ('none', 'fix the worst', 'full'):
                    raise ValueError('session requires mode and renaming choices')
                if not isinstance(state.get('pending_bundles', []), list):
                    raise ValueError('pending_bundles must be a list')
                if linked(folder):
                    raise ValueError('linked_metadata')
                if a.dry_run:
                    print('Dry run: would save a new session snapshot; nothing written.')
                    return 0
                folder.mkdir(parents=True, exist_ok=True)
                import uuid
                target = folder / ('session_' + datetime.datetime.now().strftime('%Y%m%d%H%M%S%f') + '_' + uuid.uuid4().hex + '.json')
                write_new(target, state)
                print('Session saved: ' + str(target))
                return 0
            if linked(folder):
                raise ValueError('linked_metadata')
            sessions = sorted(folder.glob('session_*.json'))
            if not sessions:
                raise ValueError('No saved session; inspect existing logs rather than inventing choices')
            if linked(sessions[-1]):
                raise ValueError('linked_metadata')
            state = json.loads(sessions[-1].read_text(encoding='utf-8-sig'))
            result = reconcile(cowork, state)
            print(json.dumps(result, indent=2))
            return 1 if result['blocked'] else 0
        if a.undo:
            return undo_bundle(a.undo, a.dry_run)
        if not a.manifest or not a.cowork:
            ap.error('manifest and --cowork are required')
        cowork = Path(os.path.abspath(Path(a.cowork).expanduser()))
        m = json.loads(Path(a.manifest).read_text(encoding='utf-8-sig'))
        problems = check(m, cowork)
        for kind, i in problems:
            print(f'[{kind}] move #{i + 1}')
        if not problems:
            approval = Path(os.path.abspath(a.approval or (a.manifest + '.preview.json')))
            manifest_path = Path(os.path.abspath(a.manifest))
            if any(inside(approval, Path(r['_src'])) or inside(manifest_path, Path(r['_src'])) for r in m['moves']):
                raise ValueError('metadata_inside_source')
            current = snapshot(m, cowork, [approval, manifest_path])
            if linked(approval):
                raise ValueError('linked_metadata')
            if approval.exists():
                approved = json.loads(approval.read_text(encoding='utf-8-sig'))
                if current != approved:
                    raise ValueError('approval_changed: files, references or manifest changed; prepare a new preview for approval')
            elif a.dry_run:
                write_new(approval, current)
            else:
                raise ValueError('approval_required: dry-run and approve the saved preview first')
            m['_approval_path'] = str(approval)
            m['_dependencies'] = current['dependencies']
            for row, fingerprint in zip(m['moves'], current['sources']):
                row['_fingerprint'] = fingerprint
        if a.dry_run:
            if not problems:
                print(f"Preview: {approval}; {len(current['dependencies']['files'])} text files inspected; {len(current['dependencies']['uninspected'])} uninspected items. External consumers are not certified.")
            print(f"Dry run: {len(m['moves'])} move(s) planned for bundle {m['bundle']}.")
            for row in m['moves'][:50]:
                print(f"{row['_src']} -> {row['_dst']}")
            return int(bool(problems))
        if problems:
            print('Refusing to run. Resolve every problem; route exact duplicates to 00_Inbox/_duplicates/.')
            return 1
        return run(m, cowork)
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f'STOPPED: {e}. Existing undo plans and log entries are preserved.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
