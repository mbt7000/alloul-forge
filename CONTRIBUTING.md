# Contributing

Contributions welcome — skills, tools, translations, and eval sets.
المساهمات مرحّب بها — مهارات، أدوات، ترجمات، ومجموعات تقييم.

## Adding a skill

1. Create `skills/<kebab-case-name>/SKILL.md` with YAML frontmatter:
   `name` (must match the directory) and `description` (what it does +
   a "Use when …" trigger — auto-invocation depends on it).
2. Follow the house format: input/output contract → phases with decision
   rules → explicit stop conditions → graceful fallback when subagent
   tools are missing.
3. Encode a *structural* pattern (how work is arranged and verified),
   with real decision rules — not just a prompt style.
4. Validate locally: `python3 tools/skill_lint.py skills/<name>`,
   `python3 tools/security_scan.py`, and `python3 -m unittest discover -s tests -v`.
   CI reports failures; repository owners must configure required checks
   if they want merge enforcement. The house frontmatter accepts only
   unique single-line name/description string fields; quote values containing
   YAML-special syntax. Unsupported YAML forms are rejected.
5. Strongly encouraged: an eval set at `skills/<name>/eval.md`
   (scenarios + rubrics, see the `skill-eval` skill) proving the skill
   beats baseline.

## Ground rules

- No secrets, tokens, or private hostnames in skills — parameterize.
- Skills mined from private sessions (see `skill-forge`) must be
  scrubbed of anything personal before publishing.
- English body text; translations of READMEs and skills are welcome as
  parallel files (e.g. `README.ar.md` pattern).
- MIT licensed — by contributing you agree your contribution is too.
- Keep procedures provider-neutral. Describe a host-specific capability as
  conditional; never imply that a skill grants tools, account access, approval,
  scheduling, independent contexts, or persistent memory.
- Include each required resource in an install/export test. Never add automatic
  downloads, package installation, telemetry, credential collection, eval/exec,
  unsafe deserialization, or shell-based execution of imported content.
- Changes to write/import/installer behavior require behavioral regression
  tests with disposable synthetic data. Static checks are not a malware
  certificate; state their limits and keep live-host evaluation separate.
