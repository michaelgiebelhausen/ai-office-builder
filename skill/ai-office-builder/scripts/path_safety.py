"""Reject path redirection on every supported Python version, including 3.10.

Windows name-surrogate tags identify junctions and symbolic links. Cloud storage
tags that do not redirect names are not junctions; files must still be local.
"""
from pathlib import Path
import stat


def linked(path):
    p = Path(path)
    for part in reversed((p, *p.parents)):
        try:
            info = part.lstat()
        except (FileNotFoundError, NotADirectoryError):
            continue
        if stat.S_ISLNK(info.st_mode):
            return True
        if getattr(info, 'st_file_attributes', 0) & 0x400:
            tag = getattr(info, 'st_reparse_tag', 0)
            if not tag or tag & 0x20000000:
                return True
    return False
