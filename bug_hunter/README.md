# Bug Hunter

A tool that scans a Python codebase for real, well-known bug patterns,
auto-fixes what's safe to auto-fix, flags what needs a human, and
generates a pull-request-ready description of everything it found —
currently in **dry-run mode** (simulates the whole PR workflow locally,
nothing gets pushed to GitHub yet).

## The problem this solves
Certain Python bugs are extremely common, silent (no crash, no warning),
and hard to catch in code review because they look reasonable at a
glance. Think: `def f(x=[])`, `except:`, `== None`. This tool finds them
deterministically via AST analysis — no LLM, no false-positive risk
from "creative" pattern matching — and fixes the ones that are safe to
fix mechanically.

## How it works
```
your_repo/  ──►  analyzer.py  ──►  list[Bug]  ──►  fixer.py  ──►  fixed code + diff
                 (AST + rules/)                     (only for                │
                                                      auto-fixable ones)     ▼
                                                                     report.py
                                                                (bug report + PR body)
                                                                             │
                                                                             ▼
                                                                     pr_dryrun.py
                                                          (local git branch + commit,
                                                           NOTHING pushed anywhere)
```

## Bugs it detects (7 rules)
| Rule | Auto-fixable? | Why it's a real bug |
|---|---|---|
| Mutable default argument | ✅ | Default evaluated once, shared across calls |
| Bare `except:` | ✅ | Catches `KeyboardInterrupt`/`SystemExit`, hides typos |
| `== None` / `== True` / `== False` | ✅ | Should use `is`; `==` can misbehave with overridden `__eq__` |
| `raise e` inside except | ✅ | Resets traceback, hides where the error really happened |
| Mutable class attribute | ✋ manual | Shared across ALL instances of the class |
| `open()` without `with` | ✋ manual | File descriptor leaks on exception |
| Mutating a list while iterating it | ✋ manual | Silently skips/reprocesses elements |

The manual ones are flagged, not guessed at — the correct fix depends
on context a static tool can't safely infer (e.g. does `__init__`
already exist? what's the intended control flow?).

## Quickstart
```bash
# No external deps needed to scan/fix — ast, difflib, subprocess are stdlib.
# requests is only needed for github_pr.py (real PR mode, not yet wired up).
pip install -r requirements.txt

# 1. Just see the bugs (no changes made)
python main.py scan sample_buggy_repo

# 2. Fix what's auto-fixable, write files in place
python main.py fix sample_buggy_repo

# 3. Full dry-run: fix + local git branch + commit + PR_BODY.md + diff
#    (copy the sample repo first so you don't overwrite the demo file)
cp -r sample_buggy_repo /tmp/demo_repo
python main.py fix /tmp/demo_repo --dry-run-pr --output-dir /tmp/bug_hunter_out
cat /tmp/bug_hunter_out/PR_BODY.md
cat /tmp/bug_hunter_out/changes.diff
```

## Bugs found in my own bug-finder (worth knowing about)

**#1 — false positive on plain integers.** The `== None`/`== True`/
`== False` rule initially flagged `item.stock == 0` as needing to
become `item.stock is 0`. That's wrong — 0 isn't a singleton, and
`is 0` is bad practice. Cause: Python's `==` treats `0 == False` and
`1 == True` as true, so a naive `node.value in (None, True, False)`
check silently matched plain integers too. Fixed by checking
identity/type explicitly (`node.value is None or isinstance(node.value, bool)`)
instead of `in`.

**#2 — false positive on read-only class attributes, found by testing
against real code.** Running Bug Hunter against `psf/requests`
flagged `Response.__attrs__`, `Session.__attrs__`, and
`HTTPAdapter.__attrs__` (class-level lists) as the "mutable class
attribute" bug. But checking the actual usage
(`for attr in self.__attrs__: ...`) showed they're only ever *read* —
never `.append`'d or mutated anywhere. A mutable class attribute is
only a real bug if something actually mutates it; a read-only list of
names used for serialization is fine. Fixed by having the rule walk
the whole class body looking for an actual mutating call
(`self.attr.append(...)`, subscript assignment, etc.) before flagging
it — no mutation found anywhere → not flagged.

Both are good illustrations of why "scan a hand-crafted demo file"
isn't enough validation — real code surfaces edge cases a synthetic
test won't.


## Files
```
bug_hunter/
├── models.py              # Bug / FixResult data structures
├── rules/                 # one file per bug pattern (see table above)
├── analyzer.py            # walks a directory, runs all rules
├── fixer.py                # applies safe auto-fixes, generates diffs
├── report.py               # markdown bug report + PR description
├── pr_dryrun.py             # local git branch/commit simulation (no push)
├── github_pr.py             # documented but NOT YET WIRED UP real-PR step
├── main.py                  # CLI (scan / fix subcommands)
└── sample_buggy_repo/       # demo file with one instance of every bug
```

## Path to going live (when you're ready)
1. Get comfortable with dry-run output on a real repo of yours first.
2. Get a GitHub PAT (repo scope) and set `GITHUB_TOKEN` env var.
3. Call `github_pr.push_branch()` then `github_pr.open_pull_request()`
   after `run_dry_run_pr()` — both are already implemented, just not
   wired into `main.py`'s CLI yet (intentionally — this is a "flip the
   switch when you trust it" step, not a technical blocker).

## Ideas to extend this together
- [ ] Add more rules (e.g. `assert` used for data validation — stripped
      in `python -O`; shadowing builtins; f-strings without placeholders)
- [ ] Wire up the real GitHub PR flow (see above)
- [ ] Add a `--rules` flag to enable/disable specific checks
- [ ] Run it as a GitHub Action on every PR (auto-comment instead of
      auto-fix, for cases where you want review-only mode)
- [ ] Add a config file (`.bughunter.toml`) for per-repo rule tuning
