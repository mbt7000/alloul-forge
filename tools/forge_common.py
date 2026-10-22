"""Shared, dependency-free validation and managed-file publication.

No model calls, shell commands, credentials, telemetry, or network access.
The filesystem is trusted against concurrent hostile local processes; symlinks
and unexpected/edited destination files are rejected before publication.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import tempfile
import uuid

MAX_FILE_BYTES = 4 * 1024 * 1024


class ForgeError(ValueError):
    """An input, policy, or ownership check failed."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_regular(path: pathlib.Path, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    """Read a bounded regular file, rejecting symbolic links."""
    reject_symlinks(path)
    if not path.is_file():
        raise ForgeError(f"not a regular file: {path.name}")
    with path.open("rb") as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ForgeError(f"file exceeds size limit: {path.name}")
    return data


def reject_symlinks(path: pathlib.Path) -> None:
    path = pathlib.Path(os.path.abspath(path))
    for component in [*reversed(path.parents), path]:
        if component.is_symlink():
            raise ForgeError(f"symbolic links are not accepted: {component.name}")


def relative_path(value: str) -> pathlib.PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ForgeError("invalid relative destination path")
    result = pathlib.PurePosixPath(value)
    if result.is_absolute() or any(part in ("", ".", "..") for part in value.split("/")):
        raise ForgeError("destination path must stay inside its output directory")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ForgeError("control characters in destination path")
    return result


def destination(root: pathlib.Path, relative: str) -> pathlib.Path:
    rel = relative_path(relative)
    root = pathlib.Path(os.path.abspath(root))
    reject_symlinks(root)
    result = root.joinpath(*rel.parts)
    reject_symlinks(result)
    if not result.resolve().is_relative_to(root.resolve()):
        raise ForgeError("destination escaped its output directory")
    return result


def atomic_write(path: pathlib.Path, data: bytes, *, replace: bool) -> None:
    """Publish one complete file; new files are linked without overwriting."""
    reject_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_symlinks(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".forge-tmp-", dir=path.parent)
    temporary = pathlib.Path(tmp)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except FileExistsError as exc:
                raise ForgeError(f"destination appeared during publication: {path.name}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    """Parse the deliberately small house YAML subset, failing closed.

    Only unique single-line name/description string fields are accepted.
    JSON double-quoted strings and YAML single-quoted strings are supported.
    YAML collections, tags, anchors, multiline scalars and unknown fields are
    rejected instead of being approximately interpreted. No YAML dependency.
    """
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        match = re.fullmatch(r"(name|description):[ \t]*(.+)", line)
        if not match or match[1] in fields:
            return None
        raw = match[2].strip()
        if not raw:
            return None
        if raw.startswith('"'):
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                return None
            if not isinstance(value, str):
                return None
        elif raw.startswith("'"):
            if not re.fullmatch(r"'(?:[^']|'')*'", raw):
                return None
            value = raw[1:-1].replace("''", "'")
        else:
            if (raw[0] in "[]{}&*!|>@`%#?,:-" or re.search(r":\s|\s#", raw)
                    or raw.lower() in {"null", "true", "false", "~"}):
                return None
            value = raw
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            return None
        fields[match[1]] = value
    if set(fields) != {"name", "description"}:
        return None
    return fields, text[end + 5:]


def publish_tree(
    root: pathlib.Path,
    files: dict[str, bytes],
    *,
    manifest_name: str,
    kind: str,
    metadata: dict | None = None,
    dry_run: bool = False,
) -> dict:
    """Update unchanged owned files only; preserve edits and all unowned files.

    Preflight the entire set before writes. Changed owned files and the old
    manifest are backed up. Each file is atomic; a whole multi-file run is not
    a filesystem transaction. A crash can require restoring the backup.
    """
    root = pathlib.Path(os.path.abspath(root))
    reject_symlinks(root)
    manifest_path = destination(root, manifest_name)
    if manifest_name in files or any(name.startswith(".forge-") for name in files):
        raise ForgeError("reserved output filename")
    old_bytes = None
    old_files: dict[str, str] = {}
    old_metadata: dict = {}
    if manifest_path.exists():
        old_bytes = read_regular(manifest_path)
        try:
            old = json.loads(old_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ForgeError("unreadable ownership manifest; refusing to overwrite") from exc
        if not isinstance(old, dict) or old.get("format") != 1 or old.get("kind") != kind:
            raise ForgeError("incompatible ownership manifest")
        old_files = old.get("files")
        if not isinstance(old_files, dict):
            raise ForgeError("invalid ownership manifest file table")
        old_metadata = old.get("metadata", {})
        if not isinstance(old_metadata, dict):
            raise ForgeError("invalid ownership manifest metadata")
        for name, sha in old_files.items():
            destination(root, name)
            if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha):
                raise ForgeError("invalid ownership digest")
    changes: dict[str, tuple[bytes, bytes | None]] = {}
    for name, data in sorted(files.items()):
        if not isinstance(data, bytes) or len(data) > MAX_FILE_BYTES:
            raise ForgeError("output must be bytes within the 4 MiB managed-file limit")
        target = destination(root, name)
        before = None
        if target.exists():
            if name not in old_files:
                raise ForgeError(f"unowned destination conflict: {name}; choose a new output directory")
            before = read_regular(target)
            if digest(before) != old_files[name]:
                raise ForgeError(f"user-edited destination conflict: {name}; preserve or move it before updating")
        if before != data:
            changes[name] = (data, before)
    summary = {"files": len(files), "changed": len(changes), "dry_run": dry_run,
               "retained_previous_files": sorted(set(old_files) - set(files)), "backup": None}
    owned = {**old_files, **{name: digest(data) for name, data in files.items()}}
    merged_metadata = dict(metadata or {})
    managed_roots = []
    for value in (old_metadata.get("managed_roots", []), merged_metadata.get("managed_roots", [])):
        if not isinstance(value, list):
            raise ForgeError("invalid managed-root metadata")
        for prefix in value:
            destination(root, prefix)
            managed_roots.append(prefix)
    if managed_roots:
        merged_metadata["managed_roots"] = sorted(set(managed_roots))
    manifest = {"format": 1, "kind": kind, "files": owned, "metadata": merged_metadata}
    encoded = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if len(encoded) > MAX_FILE_BYTES:
        raise ForgeError("ownership manifest exceeds managed-file byte limit")
    if dry_run:
        return summary
    root.mkdir(parents=True, exist_ok=True)
    lock = destination(root, ".forge-write.lock")
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ForgeError("another write or interrupted run holds .forge-write.lock; inspect before recovery") from exc
    try:
        with os.fdopen(lock_fd, "w") as stream:
            stream.write(str(os.getpid()))
        # Recheck after acquiring the cooperative lock, before any changes.
        if (manifest_path.exists() and read_regular(manifest_path) != old_bytes
                or old_bytes is not None and not manifest_path.exists()):
            raise ForgeError("ownership manifest changed while preparing output")
        for name, (_, before) in changes.items():
            target = destination(root, name)
            if before is None and target.exists() or before is not None and (
                    not target.exists() or read_regular(target) != before):
                raise ForgeError("destination changed while preparing output")
        backups = {name: before for name, (_, before) in changes.items() if before is not None}
        if backups:
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
            backup_prefix = f".forge-backups/{stamp}"
            for name, before in backups.items():
                atomic_write(destination(root, f"{backup_prefix}/{name}"), before, replace=False)
            if old_bytes is not None:
                atomic_write(destination(root, f"{backup_prefix}/{manifest_name}"), old_bytes, replace=False)
            summary["backup"] = backup_prefix
        for name, (data, before) in changes.items():
            atomic_write(destination(root, name), data, replace=before is not None)
        if encoded != old_bytes:
            atomic_write(manifest_path, encoded, replace=old_bytes is not None)
        return summary
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock.unlink()
