"""
fixer.py
--------
Applies textual fixes for bugs where `auto_fixable=True`. Each rule_id
has a small dedicated fix function here — this keeps the "how do I
safely rewrite this exact pattern" logic close together and easy to
audit, rather than hidden inside generic string manipulation.

IMPORTANT: fixes are applied to a list of source lines (strings,
no trailing newline) and act on ONE bug at a time. Bugs are applied
in reverse line order per file so that inserting/removing lines for
one bug doesn't shift the line numbers of bugs not yet applied.
"""

import difflib
from models import FixResult


def _fix_mutable_default(lines, bug):
    m = bug.meta
    sig_start = m["sig_start_line"] - 1   # 0-indexed
    sig_end = m["sig_end_line"] - 1
    arg_name = m["arg_name"]
    empty_repr = m["empty_repr"]
    indent = m["body_indent"]

    # Replace the mutable default with None across the (possibly multi-line)
    # signature. We look for "arg_name=<default>" — since arg names are
    # unique per function, a direct substring swap for "arg_name=" followed
    # by the container opener is safe here.
    replaced = False
    for i in range(sig_start, sig_end + 1):
        line = lines[i]
        for old_pattern in (f"{arg_name}=[]", f"{arg_name}={{}}", f"{arg_name}=set()"):
            if old_pattern in line:
                lines[i] = line.replace(old_pattern, f"{arg_name}=None", 1)
                replaced = True
                break
        if replaced:
            break

    if not replaced:
        return False, "Could not locate the exact default-value pattern to replace"

    guard_line = f"{indent}if {arg_name} is None:\n{indent}    {arg_name} = {empty_repr}"
    # insert right after the signature ends (sig_end is 0-indexed line of the closing line)
    lines.insert(sig_end + 1, guard_line)
    return True, ""


def _fix_bare_except(lines, bug):
    idx = bug.meta["line_no"] - 1
    if "except:" not in lines[idx]:
        return False, "Line no longer matches expected pattern"
    lines[idx] = lines[idx].replace("except:", "except Exception:", 1)
    return True, ""


def _fix_none_comparison(lines, bug):
    idx = bug.meta["line_no"] - 1
    old, new = bug.meta["old"], bug.meta["new"]
    if old not in lines[idx]:
        return False, "Line no longer matches expected pattern"
    lines[idx] = lines[idx].replace(old, new, 1)
    return True, ""


def _fix_raise_e(lines, bug):
    idx = bug.meta["line_no"] - 1
    exc_var = bug.meta["exc_var"]
    old = f"raise {exc_var}"
    line = lines[idx]
    if old not in line:
        return False, "Line no longer matches expected pattern"

    # Split off a trailing inline comment (naive: fine as long as the code
    # part doesn't contain a literal '#' inside a string, which is rare for
    # a bare `raise e` statement).
    code_part, _, comment_part = line.partition("#")
    stripped_code = code_part.strip()

    # Only proceed if the code portion is EXACTLY `raise e` (optionally with
    # a trailing `.` for something like `raise e.with_traceback(...)`, which
    # we deliberately do NOT touch since that's not a simple re-raise).
    if stripped_code != old:
        return False, "Line contains more than a simple re-raise; skipping to be safe"

    indent = code_part[:len(code_part) - len(code_part.lstrip())]
    new_line = f"{indent}raise"
    if comment_part:
        new_line += f"  #{comment_part}"
    lines[idx] = new_line
    return True, ""


FIXERS = {
    "mutable-default-arg": _fix_mutable_default,
    "bare-except": _fix_bare_except,
    "none-bool-equality": _fix_none_comparison,
    "raise-loses-traceback": _fix_raise_e,
}


def apply_fixes(source_lines, bugs, filepath):
    """
    Applies all auto-fixable bugs for one file.
    Returns: (new_source_lines, list[FixResult], unified_diff_text)
    """
    fixable_bugs = [b for b in bugs if b.auto_fixable and b.rule_id in FIXERS]
    # Apply bottom-to-top so line-number-based edits stay valid across fixes
    fixable_bugs.sort(key=lambda b: b.line, reverse=True)

    lines = list(source_lines)
    results = []

    for bug in fixable_bugs:
        fixer_fn = FIXERS[bug.rule_id]
        applied, reason = fixer_fn(lines, bug)
        results.append(FixResult(bug=bug, applied=applied, reason=reason))

    original_text = "\n".join(source_lines) + "\n"
    new_text = "\n".join(lines) + "\n"

    diff = difflib.unified_diff(
        original_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"a/{filepath}",
        tofile=f"b/{filepath}",
    )
    diff_text = "".join(diff)

    return lines, results, diff_text
