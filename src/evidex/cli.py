"""Command-line interface. Exit codes: 0 OK, 1 problems found, 2 usage or input error."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .manifest import EvidexError, create

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evidex",
        description="Record a SHA-256 manifest of a folder of files and verify it later.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    create_cmd = commands.add_parser(
        "create",
        help="record a manifest of a folder",
        description=(
            "Record every file in FOLDER. The manifest is written next to the "
            "folder as <folder-name>.evidex.json unless --out is given."
        ),
    )
    create_cmd.add_argument("folder", help="folder to record")
    create_cmd.add_argument("--collector", required=True, metavar="NAME",
                            help="who collected the files")
    create_cmd.add_argument("--case", dest="case_id", metavar="ID", help="optional case ID")
    create_cmd.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                            help="leave out matching files or folders (repeatable, recorded)")
    create_cmd.add_argument("--skip-special", action="store_true",
                            help="record symlinks and special files in 'skipped' instead of stopping")
    create_cmd.add_argument("--out", metavar="FILE", help="where to write the manifest")
    return parser


def _cmd_create(args: argparse.Namespace) -> int:
    out_path, digest, manifest = create(
        args.folder,
        collector=args.collector,
        case_id=args.case_id,
        excludes=args.exclude,
        skip_special=args.skip_special,
        out=args.out,
    )
    print(f"Recorded {len(manifest['files'])} files from {manifest['root_name']}")
    if manifest["skipped"]:
        print(f"Skipped {len(manifest['skipped'])} special items (listed in the manifest)")
    if manifest["excludes"]:
        print("Excluded: " + ", ".join(manifest["excludes"]))
    print(f"Manifest: {out_path}")
    print(f"Manifest digest (sha256): {digest}")
    print("Anchor this digest somewhere outside the folder.")
    return EXIT_OK


def _safe_streams() -> None:
    # A console or pipe that cannot show a file name must not crash the run.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def main(argv: Sequence[str] | None = None) -> int:
    _safe_streams()
    args = build_parser().parse_args(argv)  # argparse exits with 2 on bad arguments
    try:
        if args.command == "create":
            return _cmd_create(args)
    except EvidexError as exc:
        print(f"evidex: error: {exc}", file=sys.stderr)
        for detail in exc.details:
            print(f"  {detail}", file=sys.stderr)
        return EXIT_USAGE
    raise AssertionError(f"unhandled command {args.command!r}")  # pragma: no cover
