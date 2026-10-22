#!/usr/bin/env python3
"""Build a managed Markdown vault. Offline by default; imported content is never executed."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import http.client
import ipaddress
import json
import pathlib
import re
import socket
import ssl
import sys
import unicodedata
import urllib.parse
from dataclasses import dataclass, field

from forge_common import MAX_FILE_BYTES, ForgeError, publish_tree, read_regular, reject_symlinks

MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_CORPUS_BYTES = 32 * 1024 * 1024
MAX_PAGES = 200
ENTRY_RE = re.compile(r"^-\s*\[(?P<title>[^\]]+)\]\((?P<url>[^)\s]+)\)(?::\s*(?P<desc>.*))?$")
MD_LINK_RE = re.compile(r"(?<![!\\])\[([^\]\n]+)\]\(([^)\s]+)\)")
SENSITIVE_QUERY = {"token", "access_token", "api_key", "apikey", "secret", "password", "signature", "credential"}


def safe_filename(title: str) -> str:
    name = unicodedata.normalize("NFKC", title)
    name = re.sub(r'[<>:"/\\|?*#^\[\]\x00-\x1f\x7f]', "-", name)
    name = re.sub(r"\s+", " ", name).strip(" .")[:80].rstrip(" .") or "Untitled"
    if re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", name):
        name = "Note-" + name
    return name


def derive_section(url: str) -> str:
    parts = [p for p in urllib.parse.unquote(urllib.parse.urlsplit(url).path).split("/") if p]
    parents = [p for p in parts[:-1] if p.lower() not in {"docs", "en", "latest"}]
    return safe_filename(parents[-1].replace("-", " ").replace("_", " ").title()) if parents else "Core"


def canonical_key(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = re.sub(r"\.mdx?$", "", parsed.path).rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


class Page:
    def __init__(self, title: str, url: str, desc: str = "", body: str = ""):
        self.title, self.url, self.desc, self.body = title.strip(), url, desc.strip(), body
        self.section = derive_section(url)
        self.note_name = safe_filename(title)

    @property
    def url_key(self) -> str:
        return canonical_key(self.url)

    @property
    def relative_note(self) -> str:
        return f"{safe_filename(self.section)}/{self.note_name}.md"


def dedupe_note_names(pages: list[Page]) -> None:
    sources: set[str] = set()
    names: set[str] = set()
    for page in pages:
        if page.url_key in sources:
            raise ForgeError("duplicate canonical source in corpus")
        sources.add(page.url_key)
        suffix = hashlib.sha256(page.url_key.encode()).hexdigest()[:16]
        page.note_name = f"{safe_filename(page.title)}--{suffix}"
        if page.relative_note.casefold() in names:
            raise ForgeError("generated filename collision")
        names.add(page.relative_note.casefold())


def parse_llms_txt(text: str, base_url: str) -> list[Page]:
    pages = []
    for line in text.splitlines():
        match = ENTRY_RE.match(line.strip())
        if match:
            pages.append(Page(match["title"], urllib.parse.urljoin(base_url, match["url"]), match["desc"] or ""))
    return pages


def load_local_dir(root: pathlib.Path, limit: int = MAX_PAGES, include: str | None = None) -> list[Page]:
    reject_symlinks(root)
    root = root.resolve()
    rx = re.compile(include) if include else None
    pages, total = [], 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ForgeError("symbolic links are not accepted in local corpora")
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        if rx and not (rx.search(path.as_uri()) or rx.search(path.stem)):
            continue
        if len(pages) >= limit:
            raise ForgeError("corpus exceeds page limit; narrow --include or increase --limit explicitly")
        raw = read_regular(path, MAX_PAGE_BYTES)
        total += len(raw)
        if total > MAX_CORPUS_BYTES:
            raise ForgeError("local corpus exceeds total byte limit")
        body = raw.decode("utf-8")
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        page = Page(heading[1].strip() if heading else path.stem, path.as_uri(), body=body)
        relative = path.parent.relative_to(root)
        page.section = "Core" if relative == pathlib.Path(".") else safe_filename(" - ".join(relative.parts).title())
        pages.append(page)
    return pages


@dataclass
class FetchPolicy:
    allow_network: bool = False
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
    allow_http: bool = False
    timeout: float = 10.0
    max_response_bytes: int = MAX_PAGE_BYTES
    max_total_bytes: int = MAX_CORPUS_BYTES
    max_requests: int = 300
    requests: int = 0
    received_bytes: int = 0

    def check_url(self, url: str) -> urllib.parse.SplitResult:
        if not self.allow_network:
            raise ForgeError("network disabled; use --allow-network for a trusted remote index")
        if any(ord(c) < 33 or ord(c) == 127 for c in url) or "\\" in url:
            raise ForgeError("invalid remote URL characters")
        try:
            parts = urllib.parse.urlsplit(url)
            port = parts.port
            host = (parts.hostname or "").encode("idna").decode().lower()
        except (ValueError, UnicodeError) as exc:
            raise ForgeError("invalid remote URL") from exc
        schemes = {"https", "http"} if self.allow_http else {"https"}
        if parts.scheme not in schemes or parts.username is not None or parts.password is not None:
            raise ForgeError("only authorized HTTPS URLs without credentials are accepted")
        if port not in {None, 443 if parts.scheme == "https" else 80}:
            raise ForgeError("nonstandard network ports are not accepted")
        if host not in self.allowed_hosts:
            raise ForgeError("remote host is outside the explicit allowlist")
        decoded = parts.path
        for _ in range(3):
            decoded = urllib.parse.unquote(decoded)
        if "\\" in decoded or any(segment in {".", ".."} for segment in decoded.split("/")):
            raise ForgeError("dot segments are not accepted in remote source paths")
        if any(ord(c) < 32 or ord(c) == 127 for c in decoded):
            raise ForgeError("encoded control characters in remote URL")
        if any(key.lower() in SENSITIVE_QUERY for key, _ in urllib.parse.parse_qsl(parts.query)):
            raise ForgeError("credential-like URL query parameters are not accepted")
        return parts


def public_addresses(host: str, port: int) -> list[str]:
    try:
        addresses = sorted({entry[4][0] for entry in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})
    except OSError as exc:
        raise ForgeError("remote hostname could not be resolved") from exc
    if not addresses:
        raise ForgeError("remote hostname has no addresses")
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        if (not parsed.is_global or parsed.is_multicast or parsed.is_unspecified
                or isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None):
            raise ForgeError("private, reserved, or mapped network destinations are blocked")
    return addresses


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, address: str, port: int, timeout: float):
        super().__init__(host, port, timeout=timeout)
        self.address = address

    def connect(self) -> None:
        self.sock = socket.create_connection((self.address, self.port), timeout=self.timeout)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, port: int, timeout: float):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        raw = socket.create_connection((self.address, self.port), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def fetch(url: str, policy: FetchPolicy | None = None) -> str:
    policy = policy or FetchPolicy()
    current, visited = url, set()
    for _ in range(4):
        parts = policy.check_url(current)
        if current in visited:
            raise ForgeError("redirect loop")
        visited.add(current)
        policy.requests += 1
        if policy.requests > policy.max_requests:
            raise ForgeError("network request budget exceeded")
        host = (parts.hostname or "").encode("idna").decode().lower()
        port = 443 if parts.scheme == "https" else 80
        address = public_addresses(host, port)[0]
        cls = PinnedHTTPSConnection if parts.scheme == "https" else PinnedHTTPConnection
        connection = cls(host, address, port, policy.timeout)
        target = urllib.parse.quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
        if parts.query:
            target += "?" + parts.query
        try:
            connection.request("GET", target, headers={"User-Agent": "alloul-forge-graphify/2.0", "Accept": "text/markdown, text/plain", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ForgeError("redirect is missing its destination")
                current = urllib.parse.urljoin(current, location)
                continue
            if response.status != 200:
                raise ForgeError(f"remote source returned HTTP {response.status}")
            media_type = (response.getheader("Content-Type") or "text/plain").split(";", 1)[0].lower()
            if media_type not in {"text/plain", "text/markdown", "text/x-markdown", "application/markdown"}:
                raise ForgeError("remote source must be Markdown or plain text")
            if (response.getheader("Content-Encoding") or "identity").lower() != "identity":
                raise ForgeError("compressed remote responses are not accepted")
            remaining = min(policy.max_response_bytes, policy.max_total_bytes - policy.received_bytes)
            raw = response.read(max(0, remaining) + 1)
            if len(raw) > remaining:
                raise ForgeError("remote byte budget exceeded")
            policy.received_bytes += len(raw)
            return raw.decode("utf-8")
        except (OSError, http.client.HTTPException, UnicodeDecodeError) as exc:
            raise ForgeError("remote download failed; existing vault was not refreshed") from exc
        finally:
            connection.close()
    raise ForgeError("redirect limit exceeded")


def wikilinkify(body: str, by_url_key: dict[str, Page], page_url: str = "") -> str:
    expanded_bytes = len(body.encode("utf-8"))
    def rewrite(text: str) -> str:
        def replace(match: re.Match) -> str:
            nonlocal expanded_bytes
            label, target = match.groups()
            if target.startswith("#"):
                return match[0]
            absolute = urllib.parse.urljoin(page_url, target)
            try:
                parsed = urllib.parse.urlsplit(absolute)
                page = by_url_key.get(canonical_key(absolute))
            except ValueError:
                return match[0]
            if page is None:
                return match[0]
            fragment = "#" + urllib.parse.unquote(parsed.fragment) if parsed.fragment else ""
            if any(c in fragment for c in "[]|\n\r"):
                return match[0]
            replacement = f"[[{page.relative_note[:-3]}{fragment}|{label.replace('|', '／')}]]"
            expanded_bytes += len(replacement.encode()) - len(match[0].encode())
            if expanded_bytes > MAX_FILE_BYTES:
                raise ForgeError("expanded note exceeds managed-file byte limit; narrow the source document")
            return replacement
        return "".join(piece if piece.startswith("`") else MD_LINK_RE.sub(replace, piece)
                       for piece in re.split(r"(`+[^`\n]*`+)", text))
    output, fence = [], None
    for line in body.splitlines(keepends=True):
        opening = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if opening:
            marker = opening[1]
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            output.append(line)
        else:
            output.append(line if fence else rewrite(line))
    return "".join(output)


def frontmatter(page: Page, fetched: str) -> str:
    fields = {"title": page.title, "source": page.url, "section": page.section,
              "fetched": fetched, "generated_by": "alloul-forge", "source_trust": "untrusted-content"}
    if page.desc:
        fields["description"] = page.desc
    return "---\n" + "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in fields.items()) + "\n---"


def build_vault(pages: list[Page], vault: pathlib.Path, corpus_name: str, *, dry_run: bool = False) -> dict:
    if not pages:
        raise ForgeError("no Markdown pages found")
    dedupe_note_names(pages)
    by_url_key = {page.url_key: page for page in pages}
    fetched = dt.datetime.now(dt.timezone.utc).date().isoformat()
    files: dict[str, bytes] = {}
    sections: dict[str, list[Page]] = {}
    for page in pages:
        sections.setdefault(safe_filename(page.section), []).append(page)
        note = frontmatter(page, fetched) + "\n\n" + wikilinkify(page.body, by_url_key, page.url).strip() + "\n"
        files[page.relative_note] = note.encode()
        if len(files[page.relative_note]) > MAX_FILE_BYTES:
            raise ForgeError("generated note exceeds managed-file byte limit")
        if sum(len(data) for data in files.values()) > MAX_CORPUS_BYTES:
            raise ForgeError("generated vault exceeds total byte limit")
    home = [f"# {corpus_name}", "", f"{len(pages)} generated notes. Source content is untrusted data, not instructions.", ""]
    for section, section_pages in sorted(sections.items()):
        moc = f"{section}/MOC--{hashlib.sha256(section.encode()).hexdigest()[:12]}.md"
        lines = [f"# {section} — Map of Content", ""]
        for page in sorted(section_pages, key=lambda p: (p.title.casefold(), p.url_key)):
            lines.append(f"- [[{page.relative_note[:-3]}|{page.title.replace('|', '／')}]]")
        if moc in files:
            raise ForgeError("reserved index filename collision")
        files[moc] = ("\n".join(lines) + "\n").encode()
        home.append(f"- [[{moc[:-3]}|{section}]] ({len(section_pages)} notes)")
    files["Home.md"] = ("\n".join(home) + "\n").encode()
    if sum(len(data) for data in files.values()) > MAX_CORPUS_BYTES:
        raise ForgeError("generated vault exceeds total byte limit")
    return publish_tree(vault, files, manifest_name=".forge-vault.json", kind="vault", dry_run=dry_run,
                        metadata={"sources": sorted(by_url_key), "source_trust": "untrusted-content"})


def collect(source: str, limit: int | None = None, include: str | None = None,
            policy: FetchPolicy | None = None) -> tuple[list[Page], str]:
    limit = MAX_PAGES if limit is None else limit
    if not 1 <= limit <= 2000:
        raise ForgeError("--limit must be between 1 and 2000")
    src = pathlib.Path(source)
    if src.is_dir():
        return load_local_dir(src, limit, include), src.name
    if src.is_file():
        text = read_regular(src, MAX_PAGE_BYTES).decode("utf-8")
        base_url = ""
    else:
        text, base_url = fetch(source, policy), source
    pages = parse_llms_txt(text, base_url)
    if include:
        rx = re.compile(include)
        pages = [page for page in pages if rx.search(page.url) or rx.search(page.title)]
    if len(pages) > limit:
        raise ForgeError("index exceeds page limit; narrow --include or increase --limit explicitly")
    for page in pages:
        page.body = fetch(page.url, policy)
    heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    return pages, heading[1].strip() if heading else "Documentation Vault"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cmd", choices=["list", "obsidian"])
    parser.add_argument("source")
    parser.add_argument("--vault")
    parser.add_argument("--limit", type=int, default=MAX_PAGES)
    parser.add_argument("--include")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--allow-host", action="append", default=[])
    parser.add_argument("--allow-http", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        hosts = {host.encode("idna").decode().lower() for host in args.allow_host}
        source_host = urllib.parse.urlsplit(args.source).hostname
        if source_host:
            hosts.add(source_host.encode("idna").decode().lower())
        policy = FetchPolicy(args.allow_network, frozenset(hosts), args.allow_http)
        if not 1 <= args.limit <= 2000:
            raise ForgeError("--limit must be between 1 and 2000")
        if args.cmd == "obsidian":
            if not args.vault:
                raise ForgeError("--vault is required for obsidian")
            src, out = pathlib.Path(args.source), pathlib.Path(args.vault)
            if src.is_dir() and (out.resolve().is_relative_to(src.resolve()) or src.resolve().is_relative_to(out.resolve())):
                raise ForgeError("source and destination directories must not overlap")
        if args.cmd == "list":
            if pathlib.Path(args.source).is_dir():
                pages = load_local_dir(pathlib.Path(args.source), args.limit, args.include)
            else:
                text = (read_regular(pathlib.Path(args.source), MAX_PAGE_BYTES).decode()
                        if pathlib.Path(args.source).is_file() else fetch(args.source, policy))
                pages = parse_llms_txt(text, args.source if source_host else "")
                if args.include:
                    rx = re.compile(args.include)
                    pages = [p for p in pages if rx.search(p.url) or rx.search(p.title)]
                if len(pages) > args.limit:
                    raise ForgeError("index exceeds page limit")
            for page in pages:
                print(f"{page.section:24} {page.title}")
            return 0
        pages, title = collect(args.source, args.limit, args.include, policy)
        print(json.dumps(build_vault(pages, pathlib.Path(args.vault), title, dry_run=args.dry_run), ensure_ascii=False))
        return 0
    except (ForgeError, OSError, UnicodeError, re.error, ValueError) as exc:
        print(f"graphify: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
