#!/usr/bin/env python3
"""Local high-risk-pattern checks. Findings are signals, not a malware verdict.

Never imports or executes the files being scanned. Never prints secret values.
"""
from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import sys

from forge_common import ForgeError, read_regular

SKIP = {".git", ".forge-backups", "__pycache__", ".venv", "node_modules"}
TEXT_SUFFIXES = {".py", ".sh", ".md", ".json", ".yml", ".yaml", ".txt", ".toml"}
SECRET_PATTERNS = [
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{20,})"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
]


def dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return dotted(node.value) + "." + node.attr
    return ""


def scan_text(path: str, text: str) -> list[dict]:
    findings = []
    def add(line: int, rule: str) -> None:
        findings.append({"path": path, "line": line, "rule": rule})
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(1) if match.lastindex else ""
            if value and any(word in value.upper() for word in ("YOUR_", "EXAMPLE", "PLACEHOLDER")):
                continue
            add(text.count("\n", 0, match.start()) + 1, "credential-pattern-redacted")
    if pathlib.PurePosixPath(path).suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            add(exc.lineno or 1, "invalid-python")
            return findings
        aliases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    aliases[item.asname or item.name] = item.name
            elif isinstance(node, ast.ImportFrom):
                for item in node.names:
                    aliases[item.asname or item.name] = f"{node.module}.{item.name}"
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = dotted(node.func)
            head, _, tail = name.partition(".")
            name = aliases.get(head, head) + ("." + tail if tail else "")
            if name in {"eval", "exec", "builtins.eval", "builtins.exec", "os.system", "os.popen", "pickle.loads", "pickle.load", "marshal.loads", "yaml.load"}:
                add(node.lineno, "dynamic-execution-or-unsafe-deserialization")
            if name.startswith("subprocess.") and any(k.arg == "shell" and not (
                    isinstance(k.value, ast.Constant) and k.value.value is False) for k in node.keywords):
                add(node.lineno, "shell-execution")
    if pathlib.PurePosixPath(path).suffix == ".sh":
        for number, line in enumerate(text.splitlines(), 1):
            if re.search(r"\b(curl|wget)\b.*\|\s*(sh|bash)\b|\beval\s|\bbase64\b.*\|.*\b(sh|bash)\b", line):
                add(number, "download-or-decode-and-execute")
    return findings


def scan_tree(root: pathlib.Path) -> dict:
    findings, count = [], 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in SKIP for part in relative.parts):
            continue
        if path.is_symlink():
            findings.append({"path": relative.as_posix(), "line": 0, "rule": "symbolic-link"})
            continue
        if not path.is_file():
            continue
        if path.name in {".env", "id_rsa", "id_ed25519"}:
            findings.append({"path": relative.as_posix(), "line": 0, "rule": "sensitive-filename"})
        if path.suffix not in TEXT_SUFFIXES:
            continue
        count += 1
        try:
            text = read_regular(path).decode("utf-8")
            findings.extend(scan_text(relative.as_posix(), text))
        except (ForgeError, OSError, UnicodeError):
            findings.append({"path": relative.as_posix(), "line": 0, "rule": "unreadable-or-oversized-text"})
    return {"files_scanned": count, "findings": findings,
            "limits": "Heuristic static checks; zero findings does not establish absence of malicious code or vulnerabilities."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=str(pathlib.Path(__file__).resolve().parent.parent))
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)
    if not root.is_dir() or root.is_symlink():
        print("security_scan: expected a regular directory", file=sys.stderr)
        return 1
    result = scan_tree(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
