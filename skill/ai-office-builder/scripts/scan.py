#!/usr/bin/env python3
"""Read-only inventory of one or more folders. Moves nothing.

Usage:
    python scan.py <folder> [<folder> ...] --out scan.json [--max-files 200000]

Output JSON:
    roots            per-root file count and size
    extensions       top file extensions with counts
    clusters         folders whose files are mostly one kind (name keywords + extensions)
    git_repos        folders containing .git (not descended into)
    media_folders    folders with >= 1 GB of audio/video/raw images
    name_clashes     file names that appear in several places (same name, maybe different content)
    likely_duplicates groups with identical size + content hash
    spaces_in_names  count + sample
    deep_paths       paths more than 5 folder levels below their root
"""
import argparse, hashlib, json, os, re, sys
from collections import Counter, defaultdict

SKIP_DIRS = {"node_modules", "__pycache__", ".venv", "venv", "AppData", "Library",
             "Application Data", "$RECYCLE.BIN", "System Volume Information",
             ".Trash", "99_Private", ".obsidian", "Pictures", "Photos Library.photoslibrary", ".cache"}
MEDIA_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".wav", ".mp3", ".aif", ".aiff",
             ".m4a", ".braw", ".r3d", ".cr2", ".cr3", ".nef", ".arw", ".dng", ".psd", ".prproj"}
KEYWORDS = {
    "invoice": "invoices", "receipt": "receipts", "statement": "statements",
    "syllabus": "syllabi", "lecture": "lecture notes", "transcript": "transcripts",
    "contract": "contracts", "proposal": "proposals", "resume": "resumes",
    "cover_letter": "cover letters", "tax": "tax documents", "w2": "tax documents",
    "brief": "briefs", "meeting": "meeting notes", "notes": "notes",
}
COURSE_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{2,4})[ _-]?(\d{4})(?!\d)")


def hash_file(path, limit=4 * 1024 * 1024):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(limit), b''):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-files", type=int, default=200000)
    a = ap.parse_args()

    ext_count = Counter()
    by_name = defaultdict(list)
    by_size = defaultdict(list)
    folder_files = defaultdict(list)
    media_bytes = Counter()
    git_repos, deep, spaces = [], [], []
    roots_info = {}
    course_codes = Counter()
    n = 0

    for root in a.roots:
        if n >= a.max_files:
            break
        root = os.path.abspath(os.path.expanduser(root))
        if not os.path.isdir(root):
            roots_info[root] = {"error": "not a folder or not accessible"}
            continue
        rc, rs = 0, 0
        base_depth = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            if ".git" in dirnames or ".git" in filenames:
                git_repos.append(dirpath)
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".") and not os.path.islink(os.path.join(dirpath, d)) and not (hasattr(os.path, "isjunction") and os.path.isjunction(os.path.join(dirpath, d)))]
            depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
            for fn in filenames:
                if os.path.islink(os.path.join(dirpath, fn)) or fn.startswith(".") or fn.lower() in ("desktop.ini", "thumbs.db"):
                    continue
                p = os.path.join(dirpath, fn)
                try:
                    size = os.path.getsize(p)
                except OSError:
                    continue
                n += 1
                rc += 1
                rs += size
                ext = os.path.splitext(fn)[1].lower()
                ext_count[ext or "(none)"] += 1
                by_name[fn.lower()].append(p)
                if size >= 0:
                    by_size[size].append(p)
                folder_files[dirpath].append(fn)
                if ext in MEDIA_EXT:
                    media_bytes[dirpath] += size
                if " " in fn and len(spaces) < 5000:
                    spaces.append(p)
                if depth >= 5:
                    deep.append(p)
                for m in COURSE_RE.finditer(fn + " " + os.path.basename(dirpath)):
                    course_codes[f"{m.group(1)}_{m.group(2)}"] += 1
                if n >= a.max_files:
                    break
            if n >= a.max_files:
                break
        roots_info[root] = {"files": rc, "bytes": rs}

    clusters = []
    for d, files in folder_files.items():
        if len(files) < 5:
            continue
        kw = Counter()
        for fn in files:
            low = fn.lower()
            for k, label in KEYWORDS.items():
                if k in low:
                    kw[label] += 1
        exts = Counter(os.path.splitext(f)[1].lower() for f in files)
        top_kw = kw.most_common(1)
        top_ext = exts.most_common(1)[0]
        clusters.append({
            "folder": d, "files": len(files),
            "top_keyword": top_kw[0] if top_kw else None,
            "top_extension": top_ext,
        })
    clusters.sort(key=lambda c: -c["files"])

    dups = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        hashes = defaultdict(list)
        for p in paths:
            h = hash_file(p)
            if h:
                hashes[h].append(p)
        for h, ps in hashes.items():
            if len(ps) > 1:
                dups.append({"size": size, "paths": ps})

    clashes = [{"name": k, "count": len(v), "paths": v[:10]}
               for k, v in by_name.items() if len(v) > 1]
    clashes.sort(key=lambda c: -c["count"])

    out = {
        "roots": roots_info,
        "total_files": n,
        "truncated": n >= a.max_files,
        "extensions": ext_count.most_common(30),
        "course_codes": course_codes.most_common(20),
        "clusters": clusters[:60],
        "git_repos": git_repos,
        "media_folders": [{"folder": d, "gb": round(b / 1e9, 2)}
                          for d, b in media_bytes.most_common() if b >= 1e9],
        "name_clashes": clashes[:100],
        "likely_duplicates": dups[:200],
        "spaces_in_names": {"count": len(spaces), "sample": spaces[:15]},
        "deep_paths": {"count": len(deep), "sample": deep[:15]},
    }
    with open(a.out, "x", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Scanned {n} files across {len(a.roots)} folder(s). "
          f"{len(git_repos)} git repos, {len(dups)} duplicate groups, "
          f"{len(clashes)} repeated names. Summary written to {a.out}")


if __name__ == "__main__":
    sys.exit(main())
