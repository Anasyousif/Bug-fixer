"""
main.py
-------
Bug Hunter CLI.

Usage:
    python main.py scan <path>
        Scan a file or directory, print a markdown bug report.

    python main.py fix <path> [--dry-run-pr] [--output-dir OUTPUT_DIR]
        Scan, apply all auto-fixable fixes, and either:
          - just write the fixed files (default), or
          - --dry-run-pr: also create a local git branch + commit + PR
            body, simulating the full PR workflow without pushing anywhere.
"""

import argparse
import os
import sys

from analyzer import analyze_path
from fixer import apply_fixes
from report import bug_report_markdown, pr_body_markdown
from pr_dryrun import run_dry_run_pr


def cmd_scan(args):
    results, files_scanned, total_bugs = analyze_path(args.path)
    report = bug_report_markdown(results, files_scanned, total_bugs)
    print(report)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"\n[Report written to {args.output}]", file=sys.stderr)


def cmd_fix(args):
    results, files_scanned, total_bugs = analyze_path(args.path)

    if not results:
        print(f"Scanned {files_scanned} file(s), no issues found. Nothing to fix. 🎉")
        return

    fix_results_by_file = {}
    file_fixes = {}   # only files where >=1 fix was actually applied

    for filepath, data in results.items():
        new_lines, fix_results, diff_text = apply_fixes(
            data["source_lines"], data["bugs"], filepath
        )
        fix_results_by_file[filepath] = fix_results
        if any(r.applied for r in fix_results):
            file_fixes[filepath] = new_lines

    report = bug_report_markdown(results, files_scanned, total_bugs)
    pr_body = pr_body_markdown(results, fix_results_by_file, files_scanned, total_bugs)

    print(report)
    print("\n\n" + "=" * 70)
    print("PR DESCRIPTION (preview)")
    print("=" * 70 + "\n")
    print(pr_body)

    if not file_fixes:
        print("\n[No auto-fixable issues found — nothing to write or commit]")
        return

    if args.dry_run_pr or args.live_pr:
        repo_path = os.path.abspath(args.path if os.path.isdir(args.path) else os.path.dirname(args.path))
        summary = run_dry_run_pr(
            repo_path=repo_path,
            file_fixes=file_fixes,
            pr_title=f"Auto-fix {len(file_fixes)} file(s) found by Bug Hunter",
            pr_body=pr_body,
            output_dir=args.output_dir,
        )
        print("\n" + "=" * 70)
        print("DRY-RUN PR CREATED (local only, nothing pushed yet)")
        print("=" * 70)
        for k, v in summary.items():
            print(f"  {k}: {v}")

        if args.live_pr:
            if not args.confirm:
                print("\n[--live-pr requires --confirm as well, to make sure this doesn't "
                      "fire by accident. Nothing was pushed. Re-run with both flags "
                      "once you've reviewed the diff above.]")
                return
            if not (args.owner and args.repo_name):
                print("\n[--live-pr requires --owner and --repo-name (the GitHub "
                      "org/user and repo name to open the PR against). Nothing was pushed.]")
                return

            from github_pr import push_branch, open_pull_request
            print("\n[Pushing branch to GitHub...]")
            push_branch(repo_path, summary["branch_name"], remote=args.remote)
            print(f"[Pushed {summary['branch_name']} to {args.remote}]")

            print("[Opening pull request...]")
            pr_result = open_pull_request(
                owner=args.owner,
                repo=args.repo_name,
                branch_name=summary["branch_name"],
                base_branch=args.base,
                pr_title=f"Auto-fix {len(file_fixes)} file(s) found by Bug Hunter",
                pr_body=pr_body,
            )
            print("\n" + "=" * 70)
            print("LIVE PR OPENED")
            print("=" * 70)
            print(f"  {pr_result['pr_url']}")
    else:
        # Just write the fixed files in place, no git operations
        for filepath, new_lines in file_fixes.items():
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
        print(f"\n[Wrote fixes to {len(file_fixes)} file(s). "
              f"Re-run with --dry-run-pr to simulate the full PR workflow.]")


def main():
    parser = argparse.ArgumentParser(description="Bug Hunter — static bug detector + auto-fixer + PR generator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Scan and report bugs (no changes made)")
    p_scan.add_argument("path", help="File or directory to scan")
    p_scan.add_argument("--output", help="Also write the report to this markdown file")
    p_scan.set_defaults(func=cmd_scan)

    p_fix = sub.add_parser("fix", help="Scan and apply auto-fixes")
    p_fix.add_argument("path", help="File or directory to fix")
    p_fix.add_argument("--dry-run-pr", action="store_true",
                        help="Simulate the full PR workflow locally (git branch + commit + PR body), no push")
    p_fix.add_argument("--output-dir", default="bug_hunter_output",
                        help="Where to write PR_BODY.md / changes.diff when using --dry-run-pr")
    p_fix.add_argument("--live-pr", action="store_true",
                        help="After the local dry-run steps, ALSO push the branch and open a real PR on GitHub. "
                             "Requires --confirm, --owner, and --repo-name. Reads token from GITHUB_TOKEN env var.")
    p_fix.add_argument("--confirm", action="store_true",
                        help="Required alongside --live-pr as an explicit safety gate — prevents accidental live pushes.")
    p_fix.add_argument("--owner", help="GitHub org/user that owns the target repo (for --live-pr)")
    p_fix.add_argument("--repo-name", help="GitHub repo name, without owner (for --live-pr)")
    p_fix.add_argument("--base", default="main", help="Base branch to open the PR against (default: main)")
    p_fix.add_argument("--remote", default="origin", help="Git remote to push to (default: origin)")
    p_fix.set_defaults(func=cmd_fix)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
