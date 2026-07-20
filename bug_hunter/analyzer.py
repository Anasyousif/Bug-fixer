"""
analyzer.py
-----------
Walks a directory tree, parses every .py file into an AST, and runs
every registered rule against it, collecting all detected bugs.
"""

import ast
import os
from rules import ALL_RULES

DEFAULT_IGNORE_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules",
                        "build", "dist", ".tox", "site-packages", ".mypy_cache"}


def find_python_files(root_path, ignore_dirs=None):
    ignore_dirs = ignore_dirs or DEFAULT_IGNORE_DIRS
    py_files = []
    if os.path.isfile(root_path):
        return [root_path] if root_path.endswith(".py") else []

    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        for fname in filenames:
            if fname.endswith(".py"):
                py_files.append(os.path.join(dirpath, fname))
    return py_files


def analyze_file(filepath):
    """Returns list[Bug] for a single file. Silently skips files that
    fail to parse (e.g. Python 2 syntax, or genuinely broken syntax —
    the latter is arguably a bug too, but a different KIND of tool's job)."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except (UnicodeDecodeError, OSError):
        return [], None

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return [], None

    source_lines = source.splitlines()
    bugs = []
    for rule_module in ALL_RULES:
        bugs.extend(rule_module.check(tree, source_lines, filepath))

    return bugs, source_lines


def analyze_path(root_path):
    """
    Returns: dict[filepath] -> {"bugs": [...], "source_lines": [...]}
    Only includes files that actually had bugs OR were successfully parsed
    (parsed-but-clean files are omitted from the result to keep it compact;
    the caller can re-derive "files scanned" count from find_python_files).
    """
    results = {}
    files = find_python_files(root_path)
    total_bugs = 0

    for filepath in files:
        bugs, source_lines = analyze_file(filepath)
        if source_lines is None:
            continue
        if bugs:
            results[filepath] = {"bugs": bugs, "source_lines": source_lines}
        total_bugs += len(bugs)

    return results, len(files), total_bugs
