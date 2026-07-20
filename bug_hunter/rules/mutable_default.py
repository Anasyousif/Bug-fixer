"""
rules/mutable_default.py
-------------------------
Bug: using a mutable object (list, dict, set) as a default argument value.

    def add_item(item, bucket=[]):
        bucket.append(item)
        return bucket

Default argument values are evaluated ONCE, when the function is defined —
not on every call. So every call that doesn't pass `bucket` explicitly
shares the SAME list, silently accumulating state across calls. This is
one of the most common real-world Python bugs, and it's silent: no error,
no warning, just wrong behavior that shows up later as "phantom" data.

Auto-fix: replace the mutable default with None, and insert a guard
clause at the top of the function body that assigns the real default
if the caller didn't pass one.
"""

import ast
from models import Bug

RULE_ID = "mutable-default-arg"
MUTABLE_CONSTRUCTORS = (ast.List, ast.Dict, ast.Set)
EMPTY_REPR = {ast.List: "[]", ast.Dict: "{}", ast.Set: "set()"}


def _find_signature_end_line(node, source_lines):
    """Scan forward from the def line tracking paren balance to find the
    line where the parameter list actually closes (handles multi-line defs)."""
    balance = 0
    started = False
    for i in range(node.lineno - 1, len(source_lines)):
        line = source_lines[i]
        for ch in line:
            if ch == "(":
                balance += 1
                started = True
            elif ch == ")":
                balance -= 1
        if started and balance == 0:
            return i + 1  # 1-indexed
    return node.lineno  # fallback, shouldn't happen on valid code


def _body_indent(node, source_lines):
    first_stmt = node.body[0]
    first_line = source_lines[first_stmt.lineno - 1]
    return first_line[:len(first_line) - len(first_line.lstrip())]


def check(tree, source_lines, filepath):
    bugs = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        args = node.args
        # defaults align to the *last* N positional args
        defaults = args.defaults
        pos_args = args.args
        offset = len(pos_args) - len(defaults)
        sig_end_line = _find_signature_end_line(node, source_lines)
        indent = _body_indent(node, source_lines)

        for i, default in enumerate(defaults):
            if isinstance(default, MUTABLE_CONSTRUCTORS):
                arg_name = pos_args[offset + i].arg
                snippet = source_lines[node.lineno - 1].strip()
                bugs.append(Bug(
                    file=filepath,
                    line=node.lineno,
                    col=node.col_offset,
                    rule_id=RULE_ID,
                    title="Mutable default argument",
                    message=(
                        f"Parameter '{arg_name}' in function '{node.name}' uses a "
                        f"mutable default value. It will be shared and mutated "
                        f"across ALL calls that don't override it, causing state "
                        f"to silently leak between unrelated calls."
                    ),
                    severity="high",
                    auto_fixable=True,
                    suggested_fix_note=(
                        f"Change default to None and add "
                        f"'if {arg_name} is None: {arg_name} = <empty container>' "
                        f"at the top of the function body."
                    ),
                    code_snippet=snippet,
                    meta={
                        "arg_name": arg_name,
                        "empty_repr": EMPTY_REPR[type(default)],
                        "sig_start_line": node.lineno,
                        "sig_end_line": sig_end_line,
                        "body_indent": indent,
                    },
                ))

        # also check keyword-only args (after *args)
        for i, default in enumerate(args.kw_defaults):
            if default is not None and isinstance(default, MUTABLE_CONSTRUCTORS):
                arg_name = args.kwonlyargs[i].arg
                snippet = source_lines[node.lineno - 1].strip()
                bugs.append(Bug(
                    file=filepath,
                    line=node.lineno,
                    col=node.col_offset,
                    rule_id=RULE_ID,
                    title="Mutable default argument (keyword-only)",
                    message=(
                        f"Keyword-only parameter '{arg_name}' in function "
                        f"'{node.name}' uses a mutable default value."
                    ),
                    severity="high",
                    auto_fixable=True,
                    suggested_fix_note=(
                        f"Change default to None and add a None-check guard."
                    ),
                    code_snippet=snippet,
                ))
    return bugs
