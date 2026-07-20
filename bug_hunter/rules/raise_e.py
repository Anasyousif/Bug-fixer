"""
rules/raise_e.py
------------------
Bug: inside an except block, writing `raise e` instead of bare `raise`.

    try:
        do_work()
    except ValueError as e:
        log.error("failed")
        raise e     # <-- resets the traceback to THIS line

`raise e` re-raises the exception but resets `__traceback__` to start at
the raise statement, losing the original location where the error
actually occurred. This makes debugging production issues much harder —
your traceback points at the except block, not the real bug.

Auto-fix: replace `raise e` with bare `raise`, which re-raises the
active exception while preserving its original traceback.
"""

import ast
from models import Bug

RULE_ID = "raise-loses-traceback"


def check(tree, source_lines, filepath):
    bugs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.name is None:
            continue  # `except Foo:` with no `as e` binding

        exc_var = node.name
        for child in ast.walk(node):
            if isinstance(child, ast.Raise) and child.cause is None:
                if isinstance(child.exc, ast.Name) and child.exc.id == exc_var:
                    snippet = source_lines[child.lineno - 1].strip()
                    bugs.append(Bug(
                        file=filepath,
                        line=child.lineno,
                        col=child.col_offset,
                        rule_id=RULE_ID,
                        title="Re-raise resets traceback",
                        message=(
                            f"'raise {exc_var}' re-raises the caught exception but "
                            f"resets its traceback to this line, hiding where the "
                            f"error actually originated. Use bare 'raise' to "
                            f"preserve the original traceback."
                        ),
                        severity="medium",
                        auto_fixable=True,
                        suggested_fix_note=f"Replace 'raise {exc_var}' with 'raise'",
                        code_snippet=snippet,
                        meta={"line_no": child.lineno, "exc_var": exc_var},
                    ))
    return bugs
