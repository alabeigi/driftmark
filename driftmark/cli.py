import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .diff import compare
from .report import display, html_report, json_report, text_report
from .snapshot import capture, load, save, write_text


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="driftmark", description="Record a directory's contents and see what changed."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    snapshot = commands.add_parser("snapshot", help="save a directory snapshot")
    snapshot.add_argument("directory", type=Path)
    snapshot.add_argument("-o", "--output", type=Path, required=True, help="snapshot file")
    snapshot.add_argument(
        "-x", "--exclude", action="append", default=[], metavar="GLOB",
        help="ignore matching paths (repeatable)",
    )

    diff = commands.add_parser("diff", help="compare two saved snapshots")
    diff.add_argument("baseline", type=Path)
    diff.add_argument("candidate", type=Path)

    check = commands.add_parser("check", help="compare a snapshot to a directory")
    check.add_argument("baseline", type=Path)
    check.add_argument("directory", type=Path, nargs="?", default=Path.cwd())

    for command in (diff, check):
        command.add_argument("--json", action="store_true", help="print JSON instead of text")
        command.add_argument("--html", type=Path, metavar="FILE", help="also save an HTML report")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "snapshot":
            snapshot = capture(args.directory, tuple(args.exclude), omit=args.output)
            save(snapshot, args.output)
            print(f"Recorded {len(snapshot.files):,} files in {display(str(args.output))}.")
            return 0

        before = load(args.baseline)
        if args.command == "diff":
            inputs = (args.baseline, args.candidate)
            after = load(args.candidate)
        else:
            inputs = (args.baseline,)
            after = capture(args.directory, before.excludes, omit=args.baseline.resolve())

        changes = compare(before, after)
        if args.html is not None:
            if args.html.resolve() in {path.resolve() for path in inputs}:
                raise ValueError("HTML output would overwrite an input snapshot")
            write_text(args.html, html_report(before, after, changes))
        print(json_report(before, after, changes) if args.json else text_report(changes))
        return int(bool(changes))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"driftmark: {display(str(error))}", file=sys.stderr)
        return 2
