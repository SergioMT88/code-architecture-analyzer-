"""Shared utilities for detectors — avoids duplication detected by cross-file analysis."""
from __future__ import annotations

import ast
import sys
from typing import List


def node_unparse(node: ast.AST) -> str:
    """Return source string for an AST node — compatible with Python 3.8+.

    node_unparse() was added in Python 3.9. This shim handles the common cases
    used by detectors (Name, Attribute chains) and falls back to ast.unparse
    on 3.9+ for everything else.
    """
    if sys.version_info >= (3, 9):
        return ast.unparse(node)
    # Python 3.8 fallback for the patterns detectors actually use
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{node_unparse(node.value)}.{node.attr}"
    if isinstance(node, ast.Constant):
        return repr(node.value)
    # Generic fallback — good enough for display purposes
    return f"<{type(node).__name__}>"

if hasattr(sys, "stdlib_module_names"):
    STDLIB_MODULES = frozenset(sys.stdlib_module_names)
else:
    STDLIB_MODULES = frozenset({
        "abc", "argparse", "array", "ast", "asyncio", "atexit", "base64", "bdb", "binascii",
        "bisect", "builtins", "bz2", "calendar", "cgi", "cgitb", "chunk", "cmath", "cmd",
        "code", "codecs", "codeop", "collections", "colorsys", "compileall", "concurrent",
        "configparser", "contextlib", "contextvars", "copy", "copyreg", "cProfile", "crypt",
        "csv", "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal", "difflib",
        "dis", "distutils", "doctest", "email", "encodings", "enum", "errno", "faulthandler",
        "fcntl", "filecmp", "fileinput", "fnmatch", "fractions", "ftplib", "functools",
        "gc", "getopt", "getpass", "gettext", "glob", "graphlib", "grp", "gzip", "hashlib",
        "heapq", "hmac", "html", "http", "idlelib", "imaplib", "imghdr", "imp",
        "importlib", "inspect", "io", "ipaddress", "itertools", "json", "keyword",
        "lib2to3", "linecache", "locale", "logging", "lzma", "mailbox", "mailcap",
        "marshal", "math", "mimetypes", "mmap", "modulefinder", "msilib", "msvcrt",
        "multiprocessing", "netrc", "nis", "nntplib", "numbers", "operator", "optparse",
        "os", "ossaudiodev", "pathlib", "pdb", "pickle", "pickletools", "pipes",
        "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath", "pprint",
        "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc",
        "queue", "quopri", "random", "re", "readline", "reprlib", "resource",
        "rlcompleter", "runpy", "sched", "secrets", "select", "selectors", "shelve",
        "shlex", "shutil", "signal", "site", "smtpd", "smtplib", "sndhdr", "socket",
        "socketserver", "sqlite3", "ssl", "stat", "statistics", "string", "stringprep",
        "struct", "subprocess", "sunau", "symtable", "sys", "sysconfig", "syslog",
        "tabnanny", "tarfile", "telnetlib", "tempfile", "termios", "test", "textwrap",
        "threading", "time", "timeit", "tkinter", "token", "tokenize", "trace",
        "traceback", "tracemalloc", "tty", "turtle", "turtledemo", "types", "typing",
        "unicodedata", "unittest", "urllib", "uu", "uuid", "venv", "warnings",
        "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib",
        "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
        # Additional common aliases in Python ecosystem
        "_thread", "msilib",
    })


def class_bases(node: ast.ClassDef) -> List[str]:
    """Return flat list of base class names for a ClassDef node.

    Includes both the short name (attr) and the full dotted name (e.g. 'models.Model')
    so callers can match against either form.
    """
    bases: List[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            bases.append(base.id)
        elif isinstance(base, ast.Attribute):
            bases.append(base.attr)
            bases.append(node_unparse(base))
    return bases
