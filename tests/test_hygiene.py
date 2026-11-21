"""Repository hygiene rows from the SPEC.md required test table (step 6)."""

import ast
import re
import socket
import sys
import tomllib
import unicodedata
import warnings
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src" / "sumseal"
SKIP_DIRS = {".git", ".venv", ".claude", "__pycache__", ".pytest_cache", "build", "dist"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".txt", ".json", ".cfg", ".ini"}
TEXT_NAMES = {"LICENSE", ".gitignore", ".gitattributes"}


def repo_text_files():
    files = []
    for path in REPO.rglob("*"):
        parts = set(path.relative_to(REPO).parts)
        if parts & SKIP_DIRS or any(p.endswith(".egg-info") for p in parts):
            continue
        if path.is_file() and (path.suffix in TEXT_SUFFIXES or path.name in TEXT_NAMES):
            files.append(path)
    assert files, "no files found; is REPO right?"
    return sorted(files)


def python_files():
    return sorted([*SRC.glob("*.py"), *(REPO / "tests").glob("*.py")])


def rel(path):
    return path.relative_to(REPO).as_posix()


# Row: Hygiene: no network ----------------------------------------------------------------

NETWORK_MODULES = (
    "socket", "ssl", "http", "urllib.request", "urllib.error", "ftplib", "smtplib",
    "poplib", "imaplib", "telnetlib", "xmlrpc", "socketserver", "asyncio", "webbrowser",
)


def test_network_guard_blocks_name_lookups_and_connections():
    with pytest.raises(RuntimeError, match="network access is not allowed"):
        socket.getaddrinfo("example.com", 443)
    with pytest.raises(RuntimeError, match="network access is not allowed"):
        socket.create_connection(("example.com", 443))


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module
            for alias in node.names:
                yield f"{node.module}.{alias.name}"


@pytest.mark.parametrize("path", sorted(SRC.glob("*.py")), ids=lambda p: p.name)
def test_source_imports_stdlib_only_and_no_network(path):
    for name in imported_modules(path):
        top = name.split(".")[0]
        if top in ("__future__", "sumseal"):
            continue
        assert top in sys.stdlib_module_names, f"{path.name}: non-stdlib import {name}"
        for banned in NETWORK_MODULES:
            assert name != banned and not name.startswith(banned + "."), (
                f"{path.name}: network module {name}"
            )


# Row: Hygiene: zero runtime dependencies -------------------------------------------------


def test_no_runtime_dependencies():
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["dependencies"] == []
    assert project["optional-dependencies"] == {"dev": ["pytest"]}


# Row: Hygiene: wording -------------------------------------------------------------------

FORBIDDEN = ["court" + "-ready", "court" + " ready", "admiss" + "ible", "admiss" + "ibility"]
PUBLIC_PATHS = ["README.md", "SECURITY.md", "CHANGELOG.md", "LICENSE", "pyproject.toml"]


def public_files():
    files = [REPO / p for p in PUBLIC_PATHS]
    files += sorted(SRC.glob("*.py"))
    files += sorted(p for p in (REPO / "examples").rglob("*") if p.is_file())
    files += sorted(p for p in (REPO / ".github").rglob("*") if p.is_file())
    return files


def test_no_legal_claims_in_code_or_public_docs():
    for path in public_files():
        text = path.read_text(encoding="utf-8").lower()
        for word in FORBIDDEN:
            assert word not in text, f"{rel(path)} contains {word!r}"


def test_readme_carries_the_required_disclaimer():
    readme = " ".join((REPO / "README.md").read_text(encoding="utf-8").split())
    for sentence in (
        "sumseal records and checks file integrity.",
        "It does not prove who created a file or that its content is genuine, "
        "and it is not legal advice.",
        "Whether a manifest is accepted as evidence is decided by courts and counsel, "
        "not by this tool.",
    ):
        assert sentence in readme


# Row: Hygiene: URLs, email addresses, home paths -----------------------------------------

URL = re.compile(r"https?://([A-Za-z0-9.-]+)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
ALLOWED_HOST = re.compile(r"(?:[A-Za-z0-9-]+\.)*example\.(?:com|net|org)")
HOME_PATH = re.compile(r"[A-Za-z]:\\Users\\|/home/[A-Za-z]|/Users/[A-Za-z]")


def test_only_example_urls():
    for path in repo_text_files():
        for host in URL.findall(path.read_text(encoding="utf-8")):
            assert ALLOWED_HOST.fullmatch(host), f"{rel(path)}: real-looking URL host {host!r}"


def test_no_email_addresses():
    for path in repo_text_files():
        for match in EMAIL.finditer(path.read_text(encoding="utf-8")):
            domain = match.group(0).split("@", 1)[1]
            assert ALLOWED_HOST.fullmatch(domain), f"{rel(path)}: email address {match.group(0)!r}"


def test_no_user_home_paths():
    for path in repo_text_files():
        found = HOME_PATH.search(path.read_text(encoding="utf-8"))
        assert not found, f"{rel(path)}: user home path {found.group(0)!r}"


# Row: Hygiene: invisible characters and clean Python -------------------------------------


@pytest.mark.parametrize("path", python_files(), ids=rel)
def test_python_files_are_ascii_and_compile_without_warnings(path):
    source = path.read_bytes()
    bad = [i for i, byte in enumerate(source) if byte > 0x7F]
    assert not bad, f"{rel(path)}: non-ASCII byte at offset {bad[0]}; use \\uXXXX escapes"
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # e.g. an invalid escape like "\*"
        compile(source, str(path), "exec")


def test_no_invisible_or_control_characters_in_text_files():
    for path in repo_text_files():
        text = path.read_text(encoding="utf-8")
        for index, char in enumerate(text):
            if char in "\n\r\t":
                continue
            category = unicodedata.category(char)
            assert category not in ("Cc", "Cf", "Co", "Cn") and (
                category[0] != "Z" or char == " "
            ), f"{rel(path)}: invisible or control character {ascii(char)} at {index}"
