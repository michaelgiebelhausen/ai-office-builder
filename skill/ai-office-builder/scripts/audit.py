#!/usr/bin/env python3
"""Check a Cowork folder against the AI Office structure. Changes nothing.

Usage:
    python audit.py <Cowork path> --mode professional|student [--code ~/Code] [--json out.json]

Structure findings are failures. Naming findings are suggestions.
"""
import argparse, json, os, re, sys
from pathlib import Path
from path_safety import linked

NUM = re.compile(r"^(\d{2})_(.+)$")
STAGES = ["01_brief", "02_spec", "03_build", "04_output"]
PROJ = re.compile(r"^\d{4}_Q[1-4]_")


def lines(p):
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def has(d, name):
    p = os.path.join(d, name)
    return os.path.isfile(p) if name.endswith(".md") else os.path.isdir(p)


def claude_md(d):
    for c in (os.path.join(d, ".claude", "CLAUDE.md"),):
        if os.path.isfile(c):
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cowork")
    ap.add_argument("--mode", choices=["professional", "student"], required=True)
    ap.add_argument("--code")
    ap.add_argument("--json")
    a = ap.parse_args()
    root = os.path.normpath(os.path.expanduser(a.cowork))
    fail, warn, ok = [], [], []
    F = lambda m: fail.append(m)
    W = lambda m: warn.append(m)

    if linked(Path(root)) or not os.path.isdir(root):
        print(f"Not a folder: {root}")
        return 2

    # root
    if not has(root, "start_here.md"):
        F("Root is missing start_here.md (the front door).")
    rc = claude_md(root)
    if not rc:
        F("Root is missing .claude/CLAUDE.md (the floor plan).")
    root_text = open(rc, encoding="utf-8", errors="ignore").read() if rc else ""

    tops = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)) and d != ".claude")
    agents = []
    for d in tops:
        m = NUM.match(d)
        if not m:
            F(f"Top-level folder '{d}' isn't numbered (NN_Name). Move it into a numbered folder or 00_Inbox/to_sort/.")
            continue
        n = int(m.group(1))
        p = os.path.join(root, d)
        if n < 10:
            continue
        if 10 <= n <= 19:
            agents.append((d, m.group(2)))
            if not claude_md(p):
                F(f"Agent {d} has no .claude/CLAUDE.md (its job description).")
            is_class = a.mode == "student" and "class" in d.lower()
            # the student Class agent holds one folder per course instead of the three drawers
            need = ["Projects", "Resources", "Archive"]
            for drawer in need:
                if not has(p, drawer):
                    F(f"Agent {d} is missing {drawer}/.")
            if not has(p, "Resources/context.md"):
                F(f"Agent {d} is missing Resources/context.md.")
            if is_class:
                for sub in ("major_classes", "gened_classes", "job_search"):
                    if not has(p, "Archive/" + sub):
                        F(f"Class agent {d} is missing Archive/{sub}/.")
                for course in os.listdir(p):
                    cp = os.path.join(p, course)
                    if os.path.isdir(cp) and course not in (".claude", "Projects", "Resources", "Archive"):
                        for sub in ("Projects", "Resources", "Resources/context.md"):
                            if not has(cp, sub):
                                F(f"Course {course} is missing {sub}.")
            if d not in root_text:
                F(f"Root floor plan doesn't mention agent {d} in its routing.")
        elif 20 <= n <= 29:
            for drawer in ("Projects", "Resources"):
                if not has(p, drawer):
                    F(f"{d} is missing {drawer}/.")
            if not claude_md(p):
                F(f"Client {d} is missing .claude/CLAUDE.md.")
            pj = os.path.join(p, "Projects")
            if os.path.isdir(pj):
                for proj in os.listdir(pj):
                    pp = os.path.join(pj, proj)
                    if os.path.isdir(pp) and not all(has(pp, s) for s in STAGES):
                        F(f"Client project {d}/Projects/{proj} doesn't have all four stages ({', '.join(STAGES)}).")
        elif 30 <= n <= 39:
            if a.mode == "student":
                F(f"{d}: students must keep personal areas as agents in the 10s.")
            for drawer in ("Projects", "Resources"):
                if not has(p, drawer):
                    F(f"{d} is missing {drawer}/.")
        else:
            F(f"{d} is outside the 00–39 ranges this structure uses.")

    if not has(root, "00_Inbox"):
        F("Missing 00_Inbox/.")
    for sub in ("to_sort", "_duplicates", "_migration"):
        if not has(root, "00_Inbox/" + sub):
            F(f"Inbox is missing {sub}/.")
    lib = os.path.join(root, "01_Library")
    if not os.path.isdir(lib):
        F("Missing 01_Library/ (the second brain).")
    else:
        for sub in ("raw_human", "raw_AI"):
            if not has(lib, sub):
                F(f"Library is missing {sub}/.")
        if not has(lib, "CLAUDE.md"):
            F("Library has no CLAUDE.md routing raw files to wikis.")
        wikis = [w.lower() for w in os.listdir(lib) if w.lower().endswith("_wiki")]
        for d, name in agents:
            wiki = os.path.join(lib, d + "_Wiki")
            if not os.path.isdir(wiki) or not has(wiki, "index.md"):
                F(f"Missing wiki or index for agent {d}.")

    # walk: depth, CLAUDE.md length, git, naming
    spaces, finals, badproj = [], [], []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else len(rel.split(os.sep))
        if ".git" in dirnames or ".git" in filenames:
            F(f"Git repo inside Cowork/OneDrive: {rel}. Move it to ~/Code.")
            dirnames[:] = []
            continue
        if depth > 5:
            F(f"Folder nested {depth} levels deep (max 5): {rel}")
            dirnames[:] = []
        if os.path.basename(dirpath) == "Projects":
            for d in dirnames:
                if not PROJ.match(d) and "_" not in d[:3]:
                    badproj.append(os.path.join(rel, d))
        for fn in filenames + dirnames:
            if fn == "CLAUDE.md" and lines(os.path.join(dirpath, fn)) >= 200:
                F(f"{os.path.join(rel, fn)} is {lines(os.path.join(dirpath, fn))} lines (keep under 200).")
            if " " in fn:
                spaces.append(os.path.join(rel, fn))
            if re.search(r"final|\bcopy\b|\(\d\)", fn, re.I):
                finals.append(os.path.join(rel, fn))
        for name in list(dirnames) + filenames:
            path = os.path.join(dirpath, name)
            if linked(Path(path)):
                F(f"Linked path requires review: {path}")
                if name in dirnames:
                    dirnames.remove(name)

    if a.code:
        code = os.path.expanduser(a.code)
        if not os.path.isdir(code):
            F(f"Code folder not found at {code}.")
        elif os.path.abspath(code) == os.path.abspath(root) or os.path.abspath(root) in [str(p) for p in __import__("pathlib").Path(code).absolute().parents] or any(p.name.lower().startswith("onedrive") for p in __import__("pathlib").Path(code).absolute().parents):
            F("~/Code is inside Cowork; it should sit at the user's home folder, outside OneDrive.")

    if spaces:
        W(f"{len(spaces)} names contain spaces (suggest underscores), e.g. {spaces[:3]}")
    if finals:
        W(f"{len(finals)} names use final/copy/(1) instead of _v1/_v2, e.g. {finals[:3]}")
    if badproj:
        W(f"{len(badproj)} project folders don't start YYYY_Q#_, e.g. {badproj[:3]}")

    print(f"STRUCTURE: {'PASS' if not fail else f'{len(fail)} problem(s)'}")
    for m in fail:
        print(f"  ✗ {m}")
    print(f"SUGGESTIONS: {len(warn)}")
    for m in warn:
        print(f"  • {m}")
    if a.json:
        json.dump({"pass": not fail, "problems": fail, "suggestions": warn}, open(a.json, "x", encoding="utf-8"), indent=2)
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
