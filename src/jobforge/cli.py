"""The `jobforge` command. A thin dispatcher; the logic lives in the modules
it calls (D-13)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .errors import JobforgeError
from .ledger import STAGES


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="jobforge",
        description="Tailored resumes and cover letters from facts you confirmed.")
    p.add_argument("--version", action="version", version=f"jobforge {__version__}")
    p.add_argument("--workspace", type=Path, default=None,
                   help="workspace folder (default: the one containing the current folder)")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    s = sub.add_parser("init", help="make a new workspace, or refresh its agent files")
    s.add_argument("folder", type=Path, nargs="?", default=Path("."))
    s.add_argument("--refresh", action="store_true",
                   help="only rewrite CLAUDE.md and AGENTS.md (after an upgrade or profile change)")

    sub.add_parser("confirm", help="review drafted facts in profile/pending/")
    sub.add_parser("inventory", help="print every confirmed fact")

    s = sub.add_parser("prepare", help="capture a job posting into a job folder")
    src = s.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-url", metavar="URL")
    src.add_argument("--from-text", metavar="FILE", help="a file with the posting text, or - for stdin")
    s.add_argument("--company")
    s.add_argument("--title")
    s.add_argument("--location")
    s.add_argument("--url", help="the posting's URL, when using --from-text")
    s.add_argument("--force", action="store_true", help="replace an existing job.json")

    s = sub.add_parser("check", help="validate a job's plan.json without writing documents")
    s.add_argument("job", help="job folder name, or a unique part of it")

    s = sub.add_parser("apply", help="check a plan, then write the resume and cover letter")
    s.add_argument("job")

    s = sub.add_parser("applied", help="record what happened to an application")
    s.add_argument("--mark", required=True, metavar="JOB", help="job folder, or a unique part of its name")
    s.add_argument("--status", required=True, choices=STAGES)
    s.add_argument("--date", help="YYYY-MM-DD (default: today)")
    s.add_argument("--note", default="")

    for name in ("jobs", "search"):
        s = sub.add_parser(name, help="list your jobs" + (" (same as jobs)" if name == "search" else ""))
        s.add_argument("text", nargs="?", help="only jobs whose company, title, or posting mention this")
        s.add_argument("--status", help="only jobs with this status (including 'ghosted')")
        s.add_argument("--company")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    try:
        return _run(args)
    except JobforgeError as exc:
        print(f"error: {exc.render()}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130


def _ws(args):
    from .workspace import find_workspace
    return find_workspace(explicit=args.workspace)


def _run(args) -> int:
    cmd = args.command
    if cmd == "init":
        from .workspace import init_workspace
        folder = args.workspace or args.folder
        ws = init_workspace(folder, refresh=args.refresh)
        if args.refresh:
            print(f"Refreshed CLAUDE.md and AGENTS.md in {ws.root}")
        else:
            print(f"Created a Jobforge workspace in {ws.root}\n\n"
                  f"Next: put your old resume in {ws.root / 'intake'}, open your AI "
                  f"agent in that folder, and ask it to set you up.")
        return 0

    ws = _ws(args)

    if cmd == "confirm":
        from .confirm import run_confirm
        run_confirm(ws)
        return 0

    if cmd == "inventory":
        from .atoms import load_inventory
        from .inventory import render_markdown
        inv = load_inventory(ws)
        print(render_markdown(inv), end="")
        for w in inv.warnings:
            print(f"warning: {w}", file=sys.stderr)
        return 0

    if cmd == "prepare":
        from . import extract
        from .prepare import prepare
        if args.from_url:
            job, warnings = extract.from_url(args.from_url, company=args.company,
                                             title=args.title, location=args.location)
        else:
            text = sys.stdin.read() if args.from_text == "-" else _read_text(args.from_text)
            job, warnings = extract.from_text(text, company=args.company, title=args.title,
                                              location=args.location, url=args.url)
        folder, more = prepare(ws, job, force=args.force)
        for w in warnings + more:
            print(f"warning: {w}", file=sys.stderr)
        print(f"Prepared jobs/{folder.name}\n  {job.title} at {job.company}"
              + (f", {job.location}" if job.location else ""))
        return 0

    if cmd in ("check", "apply"):
        from .ledger import resolve_job
        folder = resolve_job(ws, args.job)
        if cmd == "check":
            from .apply import run_check
            result = run_check(ws, folder)
            for w in result.warnings:
                print(f"warning: {w}")
            if not result.ok:
                raise result.failure("Check")
            print(f"Check passed for {folder.name} (estimated {result.pages:.1f} page(s)).")
            return 0
        from .apply import apply
        out = apply(ws, folder)
        for w in out["warnings"]:
            print(f"warning: {w}")
        print(f"Wrote, in jobs/{folder.name}:\n"
              f"  {Path(out['resume']).name}\n  {Path(out['cover_letter']).name}\n"
              f"  {Path(out['working_copy']).name} (working copy; do not send)\n"
              f"Estimated resume length: {out['estimated_pages']:.1f} page(s). "
              f"PDF output is not set up (optional; arrives in a later release). "
              f"Upload the .docx files.")
        return 0

    if cmd == "applied":
        from .ledger import append_event, parse_date, resolve_job
        folder = resolve_job(ws, args.mark)
        ev = append_event(folder, args.status, parse_date(args.date), args.note)
        print(f"{folder.name}: {ev.stage} on {ev.date.isoformat()}")
        return 0

    if cmd in ("jobs", "search"):
        from .jobs import format_table, list_jobs
        from .profile import Profile, load_profile
        try:
            ghost = load_profile(ws).ghost_after_days
        except JobforgeError:  # listing jobs does not need a finished profile
            ghost = Profile(name="").ghost_after_days
        rows = list_jobs(ws, ghost_after_days=ghost, status=args.status,
                         company=args.company, text=args.text)
        print(format_table(rows))
        return 0

    raise AssertionError(f"unhandled command {cmd}")  # pragma: no cover


def _read_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise JobforgeError(f"{path} does not exist.")
    return p.read_text(encoding="utf-8", errors="replace")
