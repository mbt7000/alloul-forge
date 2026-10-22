# Host compatibility

Verified against official documentation on 2026-10-22. These are adapter/package contracts, not live-account acceptance results.

| Host | Deliverable | What remains host-owned |
|---|---|---|
| Claude Code | `install --target claude`: `.claude/skills/<name>/SKILL.md` plus resources | Model, tools, permissions, subagents and execution sandbox |
| OpenAI Codex | `install --target codex`: `.agents/skills/<name>/SKILL.md` plus resources | Project instruction policy, sandbox, tool access and model |
| ChatGPT/Codex plugins | `export --target chatgpt`: skills-only `.codex-plugin/plugin.json` package source | Local installation or submission/review, availability, distribution, tool access |
| GitHub Copilot | `install --target copilot`: `.github/skills/<name>/SKILL.md` plus resources | Supported Copilot surface, repository access, execution policy and model |
| Microsoft Copilot Studio | `export --target copilot-studio`: skills, selected instruction files, bounded controller | Harness-specific import UI, tenant policies, connectors, approvals, DLP, licensing |
| Other Agent Skills hosts | `export --target portable`, or `install --target universal` if `.agents/skills` is documented | Capability discovery and documented installation/import workflow |
| Chat hosts without native skills | Selected instruction/reference files from portable export | Manual attachment/pasting, file limits and tool availability; no native skill activation claim |

## Capability negotiation

Before executing a procedure, establish the tools and permissions the host actually exposes. A skill mentioning a shell, browser, workflow or subagent does not make that tool exist or authorize its use. Use sequential, clearly labeled passes if delegation is unavailable or unauthorized. Never represent same-context passes as independent blind evaluations. Without execution tools, deliver a draft or plan and state that it was not executed.

The `assistant-tuner` skill writes the appropriate host configuration only within the user's authorized scope. The installer itself never modifies `CLAUDE.md`, `AGENTS.md`, Copilot instructions, account settings, approval controls, connectors, or schedules.

## Installation and migration

Commands run from this repository's root; Python 3.11+ is required. `--destination` always names the project root, not its `skills` directory. `--scope user` instead interprets that explicit directory as a home-style root; GitHub Copilot then uses `.copilot/skills`.

Each package includes the full selected skill directory. The graphify and skill-forge adapters add their reviewed Python helpers under `scripts/`; instructions name that installed resource directory. Invocation syntax differs by host. The host resolves `<skill-directory>` to the actual directory; it is a placeholder, not a literal shell command.

No automatic legacy adoption: an old copied skill with no ownership record is a conflict even if its filename matches. Review it and install into a fresh target, or move the existing copy aside yourself. `assistant-tuner` replaces the old `claude-tuner` name. Nothing deletes the old directory or migrates private profiles silently.

For ChatGPT, the export is plugin source, not an uploaded/approved plugin. The OpenAI directory review and any publisher/listing metadata are separate. For Studio, importing a Markdown skill into a compatible harness differs from adding text to Instructions/Knowledge in a standard agent. Neither path configures live actions or data permissions.

## Official sources

- Claude Code skill locations and resources: https://code.claude.com/docs/en/skills
- OpenAI skill format and Codex discovery: https://learn.chatgpt.com/docs/build-skills
- OpenAI skills-only plugins: https://developers.openai.com/plugins/build/skills
- OpenAI plugin manifest/submission: https://developers.openai.com/plugins/deploy/submission
- GitHub Copilot skill locations: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills
- Copilot Studio Agent Skills/harnesses: https://learn.microsoft.com/en-us/microsoft-copilot-studio/agents-experience/skills-overview
- Copilot Studio standard-agent instruction limits: https://learn.microsoft.com/en-us/microsoft-copilot-studio/requirements-quotas
