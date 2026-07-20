"""
rules/unclosed_file.py
------------------------
Bug: calling open() and assigning the result directly, instead of using
a `with` block.

    f = open("data.txt")
    data = f.read()
    # if an exception happens before f.close(), the file handle leaks

Without a context manager, the file stays open if an exception is
raised between open() and close() — a real resource leak that can
exhaust file descriptors in long-running processes (servers, workers).

This rule flags it but does NOT auto-fix it, because converting to
`with` requires re-indenting every subsequent line that uses the file
handle, and determining exactly which lines belong inside the block
needs a human judgment call (or a much heavier CST-based rewrite).
"""

import ast
from models import Bug

RULE_ID = "unclosed-file-handle"


def _is_open_call(node):
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open")


def check(tree, source_lines, filepath):
    bugs = []
    for node in ast.walk(tree):
        # Look for: <name> = open(...)   as a direct statement (not already in a `with`)
        if isinstance(node, ast.Assign) and _is_open_call(node.value):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                var_name = node.targets[0].id
                snippet = source_lines[node.lineno - 1].strip()
                bugs.append(Bug(
                    file=filepath,
                    line=node.lineno,
                    col=node.col_offset,
                    rule_id=RULE_ID,
                    title="File opened without context manager",
                    message=(
                        f"'{var_name} = open(...)' doesn't guarantee the file gets "
                        f"closed if an exception occurs before '{var_name}.close()' "
                        f"is reached. This leaks a file descriptor."
                    ),
                    severity="medium",
                    auto_fixable=False,
                    suggested_fix_note=(
                        f"Wrap in 'with open(...) as {var_name}:' and indent the "
                        f"code that uses {var_name} inside the block."
                    ),
                    code_snippet=snippet,
                ))
    return bugs
