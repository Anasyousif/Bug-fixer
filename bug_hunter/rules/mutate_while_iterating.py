"""
rules/mutate_while_iterating.py
----------------------------------
Bug: removing/appending items to a list while iterating over that same
list directly.

    for item in items:
        if should_remove(item):
            items.remove(item)      # <-- mutates the list being iterated

Python's list iterator tracks a position index internally. Removing an
element shifts everything after it back by one, so the iterator skips
the element that shifted into the just-vacated position. This bug is
especially nasty because it doesn't crash — it just silently processes
the wrong elements, often only noticed much later when data looks "off".

This rule flags it but does NOT auto-fix it (the correct fix — iterate
over a copy, use a list comprehension, or filter — depends on intent),
since guessing wrong here could change program behavior.
"""

import ast
from models import Bug

RULE_ID = "mutate-list-while-iterating"
MUTATING_METHODS = {"remove", "append", "pop", "insert", "extend", "clear"}


def check(tree, source_lines, filepath):
    bugs = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        if not isinstance(node.iter, ast.Name):
            continue  # only handle the simple `for x in some_list:` case

        loop_target_list = node.iter.id

        for child in ast.walk(node):
            if child is node:
                continue
            if (isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == loop_target_list
                    and child.func.attr in MUTATING_METHODS):
                snippet = source_lines[child.lineno - 1].strip()
                bugs.append(Bug(
                    file=filepath,
                    line=child.lineno,
                    col=child.col_offset,
                    rule_id=RULE_ID,
                    title="Mutating list while iterating over it",
                    message=(
                        f"'{loop_target_list}.{child.func.attr}(...)' modifies "
                        f"'{loop_target_list}' while the for-loop is actively "
                        f"iterating over it. This can cause elements to be "
                        f"silently skipped or processed twice."
                    ),
                    severity="high",
                    auto_fixable=False,
                    suggested_fix_note=(
                        f"Iterate over a copy instead: "
                        f"'for item in list({loop_target_list}):' — or better, "
                        f"build a new list with a comprehension instead of "
                        f"mutating in place."
                    ),
                    code_snippet=snippet,
                ))
    return bugs
