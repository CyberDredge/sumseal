"""Command-line interface.

Exit codes: 0 OK, 1 problems found (or output cut short by a closed pipe),
2 usage or input error, 3 internal error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence

from . import __version__
from .manifest import SumsealError, add_source, create, load_manifest, manifest_digest
from .report import render_csv, render_markdown
from .verify import PROBLEMS, RESULTS, verify

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_USAGE = 2
EXIT_INTERNAL = 3

HEX_DIGEST = re.compile(r"[0-9a-f]{64}")


def _hex_digest(text: str) -> str:
    if not HEX_DIGEST.fullmatch(text):
        raise argparse.ArgumentTypeError("must be exactly 64 lowercase hex characters (0-9, a-f)")
    return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sumseal",
        description="Record a SHA-256 manifest of a folder of files and verify it later.",
        epilog=(
            "Exit codes: 0 everything OK, 1 problems found or output cut short by a "
            "closed pipe, 2 usage or input error, "
            "3 internal error (a bug in sumseal; please report it). "
            "sumseal records file integrity only; it does not prove who made a file "
            "or that its content is genuine."
        ),
    )
    parser.add_argument("--version", action="version", version=f"sumseal {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    create_cmd = commands.add_parser(
        "create",
        help="record a manifest of a folder",
        description=(
            "Record every file in FOLDER. The manifest is written next to the "
            "folder as <folder-name>.sumseal.json unless --out is given."
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

    verify_cmd = commands.add_parser(
        "verify",
        help="check a folder against its manifest",
        description=(
            "Check FOLDER against its manifest (<folder-name>.sumseal.json next to "
            "the folder unless --manifest is given). Exit 0 if everything matches, "
            "1 if anything is CHANGED, MISSING, NEW or UNREADABLE, or if "
            "--expect-digest does not match the manifest digest."
        ),
    )
    verify_cmd.add_argument("folder", help="folder to check")
    verify_cmd.add_argument("--manifest", metavar="FILE", help="manifest to check against")
    verify_cmd.add_argument("--expect-digest", type=_hex_digest, metavar="HEX",
                            help="the digest you anchored (64 lowercase hex characters); "
                                 "a different manifest digest is a problem")

    source_cmd = commands.add_parser(
        "add-source",
        help="record where one file came from",
        description=(
            "Record the source URL of one file already in the manifest. The manifest "
            "is rewritten and its digest changes: anchor the digest only after your "
            "last edit. An existing source is never overwritten."
        ),
    )
    source_cmd.add_argument("manifest", help="manifest file to update")
    source_cmd.add_argument("path", help="file path exactly as in the manifest (use /)")
    source_cmd.add_argument("url", help="where the file came from")
    source_cmd.add_argument("--accessed", required=True, metavar="TIME",
                            help="when it was accessed, UTC, like 2026-01-02T03:04:05Z")
    source_cmd.add_argument("--note", metavar="TEXT", help="optional note")

    digest_cmd = commands.add_parser("digest", help="print the manifest digest")
    digest_cmd.add_argument("manifest", help="manifest file")

    report_cmd = commands.add_parser(
        "report", help="print a readable report (UTF-8) of a manifest"
    )
    report_cmd.add_argument("manifest", help="manifest file")
    report_cmd.add_argument("--format", choices=("md", "csv"), default="md",
                            help="md (default) or csv")
    return parser


def show(name: str) -> str:
    """Name as printed: escaped if it has control, invisible or format characters."""
    return name if name.isprintable() else ascii(name)


def _cmd_create(args: argparse.Namespace) -> int:
    notes: list[str] = []
    out_path, digest, manifest = create(
        args.folder,
        collector=args.collector,
        case_id=args.case_id,
        excludes=args.exclude,
        skip_special=args.skip_special,
        out=args.out,
        notes=notes,
    )
    for note in notes:
        print(f"note: {note}")
    print(f"Recorded {len(manifest['files'])} files from {show(manifest['root_name'])}")
    if manifest["skipped"]:
        print(f"Skipped {len(manifest['skipped'])} special items (listed in the manifest)")
    if manifest["excludes"]:
        print("Excluded: " + ", ".join(manifest["excludes"]))
    print(f"Manifest: {show(str(out_path))}")
    print(f"Manifest digest (sha256): {digest}")
    print("Anchor this digest somewhere outside the folder.")
    return EXIT_OK


def _cmd_verify(args: argparse.Namespace) -> int:
    report = verify(args.folder, args.manifest)
    print(f"Manifest: {show(str(report.manifest_path))}")
    print(f"Manifest digest (sha256): {report.digest}")
    digest_mismatch = False
    if args.expect_digest is None:
        print("Compare this digest with the one you anchored when the manifest was made.")
    elif args.expect_digest == report.digest:
        print("Expected digest: matches the manifest digest.")
    else:
        digest_mismatch = True
        print(f"MISMATCH  manifest digest differs from --expect-digest {args.expect_digest}")
    problems = [f for f in report.findings if f.result in PROBLEMS]
    if problems:
        print()
        width = max(len(result) for result in RESULTS)
        for finding in problems:
            detail = f"  ({finding.detail})" if finding.detail else ""
            print(f"{finding.result:<{width}}  {show(finding.path)}{detail}")
    if report.notes:
        print()
        for note in report.notes:
            print(f"note: {note}")
    print()
    print("  ".join(f"{result} {count}" for result, count in report.counts().items()))
    if digest_mismatch:
        files = "files match the manifest" if report.ok else "problems found in the files too"
        print(f"Result: the manifest digest does not match the expected digest ({files}).")
        return EXIT_PROBLEMS
    if report.ok:
        print("Result: everything matches the manifest.")
        return EXIT_OK
    print("Result: problems found.")
    return EXIT_PROBLEMS


def _cmd_add_source(args: argparse.Namespace) -> int:
    old, new = add_source(
        args.manifest, args.path, args.url, accessed=args.accessed, note=args.note
    )
    print(f"Source recorded for {show(args.path)}")
    print(f"Previous digest (sha256):     {old}")
    print(f"New manifest digest (sha256): {new}")
    print("Anchor the digest only after your last edit.")
    return EXIT_OK


def _cmd_digest(args: argparse.Namespace) -> int:
    print(manifest_digest(load_manifest(args.manifest)))
    return EXIT_OK


def _cmd_report(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    text = render_csv(manifest) if args.format == "csv" else render_markdown(manifest)
    # Always UTF-8 bytes: the console or pipe encoding must never alter file names.
    sys.stdout.flush()
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()
    return EXIT_OK


COMMANDS = {
    "create": _cmd_create,
    "verify": _cmd_verify,
    "add-source": _cmd_add_source,
    "digest": _cmd_digest,
    "report": _cmd_report,
}


def _safe_streams() -> None:
    # A console or pipe that cannot show a file name must not crash the run.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass


def _stdout_to_devnull() -> None:
    # Point the stdout file descriptor at the null device, so the flush Python does
    # at exit writes there instead of raising BrokenPipeError again.
    try:
        fd = sys.stdout.fileno()
    except (AttributeError, OSError, ValueError):
        return  # not a real file (for example captured in tests): nothing to redirect
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, fd)
    finally:
        os.close(devnull)


def main(argv: Sequence[str] | None = None) -> int:
    _safe_streams()
    args = build_parser().parse_args(argv)  # argparse exits with 2 on bad arguments
    try:
        code = COMMANDS[args.command](args)
        if sys.stdout is not None:  # no stdout at all (for example pythonw): nothing to flush
            sys.stdout.flush()  # a closed pipe should surface here, not at interpreter exit
        return code
    except SumsealError as exc:
        print(f"sumseal: error: {exc}", file=sys.stderr)
        for detail in exc.details:
            print(f"  {detail}", file=sys.stderr)
        return EXIT_USAGE
    except BrokenPipeError:
        # The reader went away (for example `| head`). The output was cut short, so
        # never claim OK: exit 1, print nothing.
        _stdout_to_devnull()
        return EXIT_PROBLEMS
    except Exception as exc:  # a bug: report it plainly instead of a traceback
        print(f"sumseal: internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_INTERNAL
