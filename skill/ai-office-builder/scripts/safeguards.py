"""Preview-bound migration checks. Reads only explicit reference roots and sources."""
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote

TEXT = {'.md', '.markdown', '.txt', '.html', '.htm', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.ps1', '.py', '.sh'}
OPAQUE = {'.xlsx', '.xls', '.pptx', '.ppt', '.docx', '.doc', '.blend', '.prproj', '.aep', '.indd', '.lnk', '.url'}
SKIP = {'.git', '.obsidian', '99_Private', 'node_modules', '.venv', '__pycache__', '_migration'}


def walk_error(error):
    raise error


def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def linked(p):
    return any(q.is_symlink() or (hasattr(q, 'is_junction') and q.is_junction()) for q in (p, *p.parents))


def inventory(p):
    p = Path(p)
    if any(part.casefold() in ('99_private', '.obsidian') for part in p.parts):
        raise ValueError('private_path_in_bundle')
    if linked(p):
        raise ValueError('linked_path: ' + str(p))
    if p.is_file():
        return [{'path': '.', 'kind': 'file', 'sha256': digest(p)}]
    if not p.is_dir():
        raise ValueError('missing_source: ' + str(p))
    result = [{'path': '.', 'kind': 'dir'}]
    for base, dirs, files in os.walk(p, onerror=walk_error):
        for name in sorted(dirs + files):
            q = Path(base) / name
            if any(part.casefold() in ('99_private', '.obsidian') for part in q.parts):
                raise ValueError('private_path_in_bundle')
            if linked(q):
                raise ValueError('linked_path: ' + str(q))
            row = {'path': q.relative_to(p).as_posix(), 'kind': 'dir' if q.is_dir() else 'file'}
            if q.is_file():
                row['sha256'] = digest(q)
            result.append(row)
    return sorted(result, key=lambda r: r['path'])


def remap(p, moves):
    for row in moves:
        s, d = Path(row['_src']), Path(row['_dst'])
        if p == s or s in p.parents:
            return d / p.relative_to(s)
    return p


def normalize_reference(target, url=False):
    target = target.strip('<>')
    if not target:
        return None
    file_uri = target.lower().startswith('file://')
    if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', target) and not file_uri and not re.match(r'^[A-Za-z]:[/\\]', target):
        return None
    if url and target.startswith('//'):
        return None  # protocol-relative web URL
    if url or file_uri:
        target = unquote(re.split(r'[?#]', target, maxsplit=1)[0])
    if file_uri:
        target = target[7:]
        if target.lower().startswith('localhost/'):
            target = target[len('localhost'):]
        if re.match(r'^/[A-Za-z]:', target):
            target = target[1:]
        elif not target.startswith('/'):
            target = '//' + target
    return target or None


def references(text):
    patterns = [r'\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)',
                r"(?:src|href)\s*=\s*[\"']([^\"']+)[\"']",
                r'^\s*@([^\r\n]+\.md)\s*$',
                r"[\"']((?:[A-Za-z]:[/\\]|\.\.?[/\\]|/)[^\"'\r\n]+)[\"']"]
    url_spans = []
    for i, pattern in enumerate(patterns):
        for m in re.finditer(pattern, text, re.M | re.I):
            if i < 2:
                url_spans.append(m.span())
            elif i == 3 and any(m.start() < end and m.end() > start for start, end in url_spans):
                continue
            target = normalize_reference(m[1], url=i < 2)
            if target:
                yield target


def json_references(value):
    if isinstance(value, str):
        yield from references(value)
        if re.match(r'^(?:[A-Za-z]:[/\\]|\.\.?[/\\]|/|file://)', value, re.I):
            target = normalize_reference(value)
            if target:
                yield target
    elif isinstance(value, dict):
        for item in value.values():
            yield from json_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from json_references(item)


def candidates(root, budget, limit=10000, ignore=()):
    """Stream entries; count directories and unsupported files before inspection."""
    def visit():
        budget[0] += 1
        if budget[0] > limit:
            raise ValueError('reference_inspection_limit: narrow the authorized roots')
    if root in ignore:
        return
    visit()
    if root.is_file():
        yield root
        return
    stack = [root]
    skip = {x.casefold() for x in SKIP}
    while stack:
        with os.scandir(stack.pop()) as entries:
            for entry in entries:
                p = Path(entry.path)
                if p in ignore:
                    continue
                visit()
                if entry.name.casefold() in skip:
                    continue
                if linked(p):
                    yield p
                elif entry.is_dir(follow_symlinks=False):
                    stack.append(p)
                else:
                    yield p


def dependency_report(m, ignore=()):
    roots = [Path(os.path.abspath(r)) for r in m.get('reference_roots', [])]
    if not roots or any(not Path(r).is_absolute() for r in m.get('reference_roots', [])):
        raise ValueError('reference_roots must explicitly name authorized absolute scan roots')
    for row in m['moves']:
        s = Path(row['_src'])
        if not any(s == r or r in s.parents for r in roots):
            raise ValueError('source_outside_reference_roots: ' + str(s))
    limit = m.get('reference_limit', 10000)
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError('reference_limit must be an integer from 1 to 10000')
    files, coverage, budget = {}, [], [0]
    for root in roots:
        if linked(root) or any(p.casefold() in {x.casefold() for x in SKIP} for p in root.parts) or not root.exists():
            raise ValueError('unsafe_reference_root: ' + str(root))
        for p in candidates(root, budget, limit, ignore):
            if p in ignore:
                continue
            if linked(p):
                coverage.append({'path': str(p), 'reason': 'linked path not inspected'})
                continue
            if p.suffix.lower() not in TEXT:
                if p.suffix.lower() in OPAQUE:
                    coverage.append({'path': str(p), 'reason': 'application references require owner review'})
                continue
            if p.stat().st_size > 2 * 1024 * 1024:
                coverage.append({'path': str(p), 'reason': 'text exceeds 2 MiB inspection limit'})
                continue
            try:
                text = p.read_text(encoding='utf-8-sig')
            except (OSError, UnicodeError):
                coverage.append({'path': str(p), 'reason': 'unreadable text'})
                continue
            targets = list(references(text))
            if p.suffix.lower() == '.json':
                try:
                    meta = json.loads(text)
                except ValueError:
                    coverage.append({'path': str(p), 'reason': 'unparseable JSON'})
                    continue
                if isinstance(meta, dict) and meta.get('kind') == 'ai-office-builder-preview' and meta.get('schema') == 1 and isinstance(meta.get('manifest'), dict) and isinstance(meta.get('sources'), list):
                    continue
                targets = list(json_references(meta))
            files[str(p)] = {'sha256': digest(p), 'targets': sorted(set(targets))}
    broken, edges = [], []
    for filename, data in sorted(files.items()):
        p = Path(filename)
        for target in data['targets']:
            q = Path(os.path.abspath(p.parent / target))
            new_p, new_q = remap(p, m['moves']), remap(q, m['moves'])
            if new_p == p and new_q == q:
                continue
            actual = Path(os.path.abspath(new_p.parent / target))
            covered = any(q == r or r in q.parents for r in roots) and not any(x.casefold() in ('99_private', '.obsidian') for x in q.parts)
            edge = {'source': filename, 'target': str(q), 'after_source': str(new_p), 'after_target': str(new_q), 'check_target': covered}
            edges.append(edge)
            if actual != new_q or (covered and not q.exists()):
                broken.append(edge)
    review = m.get('dependency_review', '')
    if not isinstance(review, str):
        raise ValueError('dependency_review_required: owner response must be text')
    review = review.strip()
    return {'files': files, 'edges': edges, 'broken': broken, 'uninspected': coverage,
            'owner_review': review, 'scope': 'Only explicit roots; external consumers and unsupported reference syntax are not certified.'}


def snapshot(m, cowork, ignore=()):
    report = dependency_report(m, ignore)
    if report['broken']:
        raise ValueError('dependency_break: ' + json.dumps(report['broken']))
    if report['uninspected'] and not report['owner_review']:
        raise ValueError('dependency_review_required: ' + json.dumps(report['uninspected']))
    if not report['owner_review']:
        raise ValueError('dependency_review_required: record the owner response about consumers outside the scan')
    clean = {k: v for k, v in m.items() if k != 'moves' and not k.startswith('_')}
    clean['moves'] = [{k: v for k, v in r.items() if not k.startswith('_')} for r in m['moves']]
    return {'kind': 'ai-office-builder-preview', 'schema': 1, 'cowork': str(cowork), 'manifest': clean, 'dependencies': report,
            'sources': [inventory(r['_src']) for r in m['moves']]}


def write_new(path, data):
    path = Path(path)
    if linked(path):
        raise ValueError('linked_metadata')
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())


def verify_move(row, expected):
    if Path(row['_src']).exists() or inventory(row['_dst']) != expected:
        raise ValueError('verification_failed: ' + row['_dst'])


def verify_references(report, completed):
    def ready(old, new):
        return old == new or any(Path(old) == Path(r['_src']) or Path(r['_src']) in Path(old).parents for r in completed)
    for edge in report.get('edges', []):
        if not edge.get('check_target'):
            continue  # outside approved inspection coverage
        if ready(edge['source'], edge['after_source']) and ready(edge['target'], edge['after_target']):
            target = Path(edge['after_target'])
            if linked(target) or not target.exists():
                raise ValueError('dependency_verification_failed: ' + str(target))


def recovery_row_allowed(row, cowork, state):
    if not isinstance(row, dict) or not isinstance(row.get('src'), str) or not isinstance(row.get('dst'), str):
        return False
    current, original = Path(row['src']), Path(row['dst'])
    if not current.is_absolute() or not original.is_absolute() or '..' in current.parts or '..' in original.parts:
        return False
    if any(x.casefold() in ('99_private', '.obsidian') for x in (*current.parts, *original.parts)):
        return False
    originals = state.get('reference_roots', [])
    destinations = [str(cowork)] + state.get('destination_roots', [])
    def covered(path, roots):
        return isinstance(roots, list) and any(isinstance(r, str) and Path(r).is_absolute() and (path == Path(r) or Path(r) in path.parents) for r in roots)
    if not covered(original, originals) or not covered(current, destinations):
        return False
    fp = row.get('fingerprint')
    if not isinstance(fp, list) or not fp:
        return False
    for item in fp:
        if not isinstance(item, dict) or not isinstance(item.get('path'), str):
            return False
        p = Path(item['path'])
        if p.is_absolute() or '..' in p.parts or item.get('kind') not in ('file', 'dir'):
            return False
        if item['kind'] == 'file' and not re.fullmatch('[0-9a-fA-F]{64}', item.get('sha256', '')):
            return False
    return True


def reconcile(cowork, state):
    result = {'choices': state, 'bundles': [], 'pending': [], 'blocked': []}
    folder = Path(cowork) / '00_Inbox/_migration'
    if linked(folder):
        raise ValueError('linked_metadata')
    log_path = folder / 'migration_log.md'
    if linked(log_path):
        raise ValueError('linked_metadata')
    log = log_path.read_text(encoding='utf-8-sig') if log_path.exists() else ''
    verified = set()
    for line in log.splitlines():
        if line.startswith('VERIFIED '):
            try:
                event = json.loads(line[9:])
                verified.add((event['bundle'], event['src'], event['dst']))
            except (ValueError, KeyError, TypeError):
                pass
    for path in sorted(folder.glob('undo_*.json')):
        if linked(path):
            raise ValueError('linked_metadata')
        try:
            u = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(u, dict) or not isinstance(u.get('bundle'), str) or not isinstance(u.get('moves'), list) or not u['moves']:
                raise ValueError('Malformed recovery record')
            bundle, rows = u['bundle'], u['moves']
        except (ValueError, TypeError):
            result['bundles'].append({'bundle': path.stem, 'moved': 0, 'original': 0, 'blocked': 1})
            continue
        counts = {'bundle': bundle, 'moved': 0, 'original': 0, 'blocked': 0}
        if not isinstance(u.get('cowork'), str) or Path(os.path.abspath(u['cowork'])) != Path(os.path.abspath(cowork)):
            counts['blocked'] = len(rows)
        else:
            for row in rows:
                status = 'blocked'
                if recovery_row_allowed(row, cowork, state):
                    current, original = Path(row['src']), Path(row['dst'])
                    # Authorize lexical paths before checking links, existence or contents.
                    if not linked(current) and not linked(original):
                        expected = row['fingerprint']
                        if current.exists() and not original.exists() and inventory(current) == expected:
                            status = 'moved' if (bundle, str(original), str(current)) in verified else 'blocked'
                        elif original.exists() and not current.exists() and inventory(original) == expected:
                            status = 'original'
                counts[status] += 1
        result['bundles'].append(counts)
    finished = {x['bundle'] for x in result['bundles'] if x['moved'] and not x['original'] and not x['blocked']}
    result['pending'] = [x for x in state.get('pending_bundles', []) if x not in finished]
    for bundle in result['bundles']:
        if bundle['original'] and not bundle['moved'] and not bundle['blocked'] and bundle['bundle'] not in result['pending']:
            result['pending'].append(bundle['bundle'])
    result['blocked'] = [x['bundle'] for x in result['bundles'] if x['blocked'] or (x['moved'] and x['original'])]
    return result
