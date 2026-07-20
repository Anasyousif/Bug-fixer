"""
rules/none_comparison.py
--------------------------
Bug: using `== None` / `!= None` / `== True` / `== False` instead of
`is` / `is not`.

    if value == None:
        ...

This usually "works" but it's semantically wrong and can misbehave for
objects that override __eq__ (e.g. numpy arrays, pandas Series, custom
classes) where `== None` can raise, return an array, or return something
truthy/falsy in surprising ways. `is` compares identity, which is what
you actually mean for singletons like None/True/False, and PEP 8
explicitly recommends it.

Auto-fix: rewrite `== None` -> `is None`, `!= None` -> `is not None`,
`== True` -> `is True`, `== False` -> `is False`.
"""

import ast
from models import Bug

RULE_ID = "none-bool-equality"

_SINGLETONS = {"None": "None", "True": "True", "False": "False"}


def _is_singleton_const(node):
    # NOTE: can't use `node.value in (None, True, False)` here — Python's `==`
    # treats 0 == False and 1 == True, so that would misfire on plain ints
    # like `x == 0`. Check identity/type explicitly instead.
    if not isinstance(node, ast.Constant):
        return False
    return node.value is None or isinstance(node.value, bool)


def check(tree, source_lines, filepath):
    bugs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        # handles chained comparisons like `a == None == b` too, though rare
        operands = [node.left] + node.comparators
        for op, right in zip(node.ops, node.comparators):
            if isinstance(op, (ast.Eq, ast.NotEq)) and _is_singleton_const(right):
                snippet = source_lines[node.lineno - 1].strip()
                op_str = "==" if isinstance(op, ast.Eq) else "!="
                fix_str = "is" if isinstance(op, ast.Eq) else "is not"
                value_str = str(right.value)
                bugs.append(Bug(
                    file=filepath,
                    line=node.lineno,
                    col=node.col_offset,
                    rule_id=RULE_ID,
                    title=f"Using '{op_str}' to compare with {value_str}",
                    message=(
                        f"Comparing with '{op_str} {value_str}' should use identity "
                        f"comparison ('{fix_str} {value_str}') since {value_str} is "
                        f"a singleton. '==' can behave unexpectedly for objects "
                        f"that override __eq__."
                    ),
                    severity="medium",
                    auto_fixable=True,
                    suggested_fix_note=f"Replace '{op_str} {value_str}' with '{fix_str} {value_str}'",
                    code_snippet=snippet,
                    meta={
                        "line_no": node.lineno,
                        "old": f"{op_str} {value_str}",
                        "new": f"{fix_str} {value_str}",
                    },
                ))
    return bugs
