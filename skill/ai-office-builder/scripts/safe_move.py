"""Atomic same-filesystem moves; never replace an existing destination."""
import ctypes
import os
import sys


def move(src, dst):
    if os.name == 'nt':
        os.rename(src, dst)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith('linux'):
        result = libc.renameat2(-100, os.fsencode(src), -100, os.fsencode(dst), 1)
    elif sys.platform == 'darwin':
        result = libc.renamex_np(os.fsencode(src), os.fsencode(dst), 4)
    else:
        raise OSError('Unsupported atomic no-replace rename platform')
    if result:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err), dst)
