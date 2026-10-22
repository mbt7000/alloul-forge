# Alloul Forge

**35 portable Agent Skills for Claude, ChatGPT/Codex, and Copilot**, with an offline installer, host-specific exports, and a managed documentation-vault tool.

[العربية](README.ar.md) · [Compatibility](docs/COMPATIBILITY.md) · [Security](SECURITY.md) · [Architecture](docs/ARCHITECTURE.md)

The procedures cover engineering, research, knowledge organization, and evidence-based skill improvement. They do not train model weights, grant tools or permissions, connect company accounts, or guarantee better answers. Actual capabilities depend on the host, model, plan, and administrator settings.

## Quick start

Python 3.11+; no third-party Python packages, install hooks, API keys, telemetry, or model calls are required by these tools. Review a pinned revision before installing. Run from the repository root:

```bash
python3 tools/skill_lint.py
python3 tools/security_scan.py
python3 -m unittest discover -s tests -v
python3 tools/forge.py list
```

Install into an explicitly chosen project. Start with a few skills instead of loading everything:

```bash
python3 tools/forge.py install --target codex --destination ../my-project --skill debug-protocol --skill graphify --dry-run
python3 tools/forge.py install --target codex --destination ../my-project --skill debug-protocol --skill graphify
```

Other native coding hosts:

```bash
python3 tools/forge.py install --target claude --destination ../my-project
python3 tools/forge.py install --target copilot --destination ../my-project
python3 tools/forge.py install --target all --destination ../my-project
```

`all` creates the Claude, Codex, and GitHub Copilot layouts. `universal` creates `.agents/skills`, for hosts that document support for that path. `--scope user` treats the explicit destination as a user-home-style root; it does not discover or modify any account settings. The legacy `install.sh` remains a Claude-specific wrapper. Windows: use `python` instead of `python3` if appropriate; no shell wrapper is needed.

The installer copies each complete skill and its needed helpers. It never executes imported resources or modifies host permission files. An unowned or edited destination file causes a conflict, rather than silent replacement. Owned updates are backed up; files omitted by later selections are retained and reported, not deleted.

## ChatGPT and Copilot Studio

```bash
python3 tools/forge.py export --target chatgpt --output ../forge-chatgpt
python3 tools/forge.py verify ../forge-chatgpt
python3 tools/forge.py export --target copilot-studio --output ../forge-studio --skill work-hub --skill plan-builder
python3 tools/forge.py export --target portable --output ../forge-portable
```

The ChatGPT export is a **skills-only plugin source package** with `.codex-plugin/plugin.json`. It contains no MCP server, connector, hooks, or credentials. Installation/submission uses the host's supported workflow; the exporter does not install into an account, submit to a directory, or prove acceptance.

The Studio export contains skill directories plus individual instruction files and a controller under 8,000 characters. Use the Skills UI when your agent's harness supports it. For other instruction-based agents, use selected procedures within the host's limits. Uploading instructions does not create tools, scheduling, persistent memory, or permissions.

See the [compatibility matrix and official sources](docs/COMPATIBILITY.md) before choosing an adapter. Other AI vendors can use the portable procedures if their host supports Agent Skills or explicit instructions; there is no claim of universal native execution.

## Included skills

| Group | Skills |
|---|---|
| Task intake and bounded work | `conductor`, `autopilot`, `intent-reader` |
| Orchestration and review | `orchestrate`, `adversarial-verify`, `judge-panel`, `loop-until-dry`, `swarm-migrate` |
| Research and analysis | `deep-research`, `sci-research`, `data-analysis` |
| Engineering | `debug-protocol`, `test-architect`, `refactor-safely`, `perf-optimize`, `legacy-explore`, `git-flow`, `parallel-review` |
| Product and contracts | `spec-first`, `api-design`, `write-docs` |
| Reliability and security | `incident-response`, `ci-doctor`, `security-audit` |
| AI development | `prompt-engineer` |
| Skill improvement | `skill-forge`, `skill-eval`, `assistant-tuner` |
| Goals and learning | `growth-map`, `plan-builder`, `learning-tracker`, `companion-profile` |
| Knowledge | `graphify`, `knowledge-loop`, `work-hub` |

`assistant-tuner` replaces `claude-tuner`. Existing installations are not silently deleted: review and remove the old skill through your host if you migrate. Personal profiles default to `~/.alloul-forge/profile.md`, outside a repository; the installer does not create one.

Every skill contains a host/safety contract. Subagents are used only when authorized and supported; sequential fallback is not described as blind or independent. Skill evaluation requires clean separate contexts, equal budgets, and outcome-oriented rubrics. The historical debug-protocol eval is a recorded example, not a cross-provider benchmark or proof for all 35 skills.

## A managed second brain

Local Markdown works offline:

```bash
python3 tools/graphify.py obsidian ./my-docs --vault ../my-vault --dry-run
python3 tools/graphify.py obsidian ./my-docs --vault ../my-vault
```

A trusted remote Markdown index requires explicit network access:

```bash
python3 tools/graphify.py list https://code.claude.com/docs/llms.txt --allow-network
python3 tools/graphify.py obsidian https://code.claude.com/docs/llms.txt --vault ../docs-vault --allow-network
```

Only the index hostname is initially allowed. Add another trusted hostname with `--allow-host HOST` if needed. Private/reserved addresses, file URLs, credentials in URLs, unsafe redirects and HTTPS downgrades are blocked. DNS results are checked and the connection uses a checked numeric address with hostname TLS validation. Proxy environment variables are intentionally not used. Plain HTTP requires the separate `--allow-http` flag.

Defaults: 200 pages, 2 MiB per page, 32 MiB total response bytes, 300 requests and a 10-second socket timeout. `--include REGEX` narrows a corpus; `--limit N` changes the page cap, up to 2,000. Exceeding a cap fails explicitly; pages are not silently dropped. Only Markdown/plain text is imported, not an arbitrary HTML crawler.

The output uses stable source-derived names, source-relative links, heading anchors, MOCs, and `Home.md`. `.forge-vault.json` records generated-file ownership hashes. Conflicts with human files or edits stop preparation. Failed downloads do not replace good content. Updated generated files have backups under `.forge-backups/`. Atomic writes are per file, not one transaction across a whole vault; see recovery limits in [SECURITY.md](SECURITY.md).

For an old unmanaged vault, generate a new directory and review migration. Do not overwrite the old vault or forge an ownership manifest. Source content remains untrusted data and may contain prompt injection or private information; review it before sharing or giving it to an agent.

## Validation and limits

CI runs metadata checks, heuristic security checks, and offline behavior/security regression tests on Linux and Windows/Python versions configured in the workflow. These are software tests, not live Claude/ChatGPT/Copilot acceptance tests. No model calls or customer data are used.

`forge.py verify` detects modified, missing, and unexpected files inside managed skill directories relative to a local hash manifest. A hash manifest is **not** a trusted signature. Static checks and passing tests do not certify that code is malware-free. Host authorization, sandboxing, DLP, data retention and company approvals remain required where applicable.

[Contributions](CONTRIBUTING.md) · MIT license for project code; the existing third-party documentation sample has its own [attribution](examples/claude-code-vault-sample/ATTRIBUTION.md).
