# Security model and reporting

Alloul Forge is an inspectable library and local tooling, not an antivirus product, permission server or security certification. Passing checks does not prove the absence of malware or vulnerabilities.

## What the tools do

- The installer/exporter reads local project files and writes an explicitly chosen destination. It never executes skill resources, downloads dependencies, installs hooks, changes permissions, connects accounts, schedules jobs, publishes an agent, or calls a model API.
- No third-party Python runtime packages, credentials, telemetry, background service or auto-update mechanism are required by these tools. GitHub CI uses pinned upstream actions and read-only repository permissions.
- `security_scan.py` parses source as data and checks known high-risk patterns, unsafe Python execution/deserialization, download-and-execute shell patterns, credential-like values and symlinks. It prints rule names/locations, never matching secret values. These heuristics can miss malicious intent, aliases, dynamic behavior, encoded payloads and prompt injection.
- Skill instructions explicitly treat external documents, repositories and tool outputs as untrusted data. Instructions alone are not an enforceable sandbox or DLP layer; the host must enforce tool permissions and company policies.

## Filesystem guarantees and limits

Destinations must remain inside the chosen root. Symlinks are rejected. Existing unowned or user-edited files are conflicts; no force-overwrite flag is provided. A managed file can be updated only if its current content matches its previous ownership hash. Modified owned files and the old manifest are backed up before replacement. All previously managed files omitted by a later run are retained and reported.

The local manifest is an ownership/change record, not a signed trust root. Anyone able to alter that manifest can alter its claims. Inspect a pinned source revision and review the package before enabling its skills. The tools assume a filesystem not controlled by a concurrent hostile local process. Preflight, symlink checks and a cooperative lock reduce ordinary mistakes and concurrent tool conflicts; they are not protection against a privileged process racing filesystem operations.

Publication is atomic **per file**, not an all-files transaction. If disk failure or interruption occurs after some files are published, preserve the directory and `.forge-backups/`; compare against the saved manifest and restore the backed-up generation before retrying. A leftover `.forge-write.lock` indicates another process or an interrupted run; inspect it before manual recovery. Never fabricate a manifest to bypass a conflict. Use a new destination for unmanaged legacy content.

## Network boundary

Only graphify's explicit remote-import mode uses the network. It is disabled by default. With `--allow-network`, only the source hostname and explicit `--allow-host` values are eligible. HTTPS is required unless the user also chooses `--allow-http`; certificate/hostname verification stays enabled. URL credentials, common credential query keys, nonstandard ports, dot segments, file/other schemes and control characters are blocked. Every redirect is revalidated; a downgrade to HTTP is blocked without the separate HTTP opt-in.

All DNS results must be public/global, not private, reserved, multicast, unspecified or IPv4-mapped IPv6. The actual connection is pinned to a checked numeric address while TLS verifies the original hostname, avoiding a second hostname lookup for the connection. Environment proxy settings are not used. This prevents the tested private-network/redirect paths; it is not an assurance that an allowlisted public service is trustworthy. The tools never send local file contents as requests, but imported URLs and source text can themselves contain sensitive data; review them before sharing.

Default bounds: 200 pages, 2 MiB/page, 32 MiB total response bytes, 300 requests, four redirect attempts per fetch and a 10-second socket timeout. These are not a global wall-clock deadline. Remote responses must be uncompressed Markdown/plain text. A failed page aborts collection; existing vault files are not refreshed with failure placeholders. Local corpora also have file/byte/page limits and reject symlinks. Input and output directory trees must not overlap.

## Host responsibilities

Configure identity, least-privilege connectors, sandboxing, DLP, retention, approval enforcement, network egress and audit in the actual host. Importing a skill grants none of them. Never place company secrets, raw customer records or private session transcripts into a public skill repository or an unapproved provider. Operational completion must be backed by an authorized source; an AI-generated summary is not a human approval.

## Report a concern

Do not include credentials, private records or a working harmful payload in a public issue. Use a minimal synthetic reproduction. If the issue is sensitive, use GitHub private vulnerability reporting when enabled; otherwise arrange a private channel with the repository owner before sharing details. No private reporting endpoint is claimed here.
