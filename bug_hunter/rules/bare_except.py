"""
rules/bare_except.py
---------------------
Bug: a bare `except:` catches EVERYTHING, including KeyboardInterrupt,
SystemExit, and MemoryError. It hides real bugs (typos become silent
NameErrors), makes Ctrl-C not work, and makes debugging painful because
the original error and traceback are discarded.

    try:
        risky_call()
    except:
        pass

Auto-fix: replace bare `except:` with `except Exception:` — this still
catches essentially all "normal" errors but lets KeyboardInterrupt and
SystemExit propagate as intended.
"""

import ast
from models import Bug

RULE_ID = "bare-except"


def check(tree, source_lines, filepath):
    bugs = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            snippet = source_lines[node.lineno - 1].strip()
            bugs.append(Bug(
                file=filepath,
                line=node.lineno,
                col=node.col_offset,
                rule_id=RULE_ID,
                title="Bare except clause",
                message=(
                    "A bare 'except:' catches ALL exceptions, including "
                    "KeyboardInterrupt and SystemExit, and swallows the real "
                    "error type. Real bugs (e.g. a typo causing a NameError) "
                    "get silently hidden instead of surfacing."
                ),
                severity="high",
                auto_fixable=True,
                suggested_fix_note="Replace 'except:' with 'except Exception:'",
                code_snippet=snippet,
                meta={"line_no": node.lineno},
            ))
    return bugs
