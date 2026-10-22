# Architecture

## Portable procedures and host adapters

`skills/<name>/SKILL.md` is the canonical procedure. All 35 skills include a capability/authorization boundary and distinguish evidence from assumptions. They do not change model weights or supply tool access. Host-specific installation is handled by `tools/forge.py`, not by copies of divergent provider-specific procedures.

The adapter loads validated single-line house frontmatter, collects the complete selected skill directories, adds reviewed helper scripts where required, runs heuristic resource checks, and publishes into the selected layout. ChatGPT export creates skills-only plugin source; Studio export creates skills and bounded instruction documents. Neither publishes into an account.

`tools/forge_common.py` supplies bounded regular-file reads, strict house metadata parsing, safe relative destinations, ownership hashes, preflight conflict detection, backups, cooperative locks and atomic single-file publication. The strict parser accepts unique name/description string fields, JSON double-quoted strings, YAML single-quoted strings or safe plain scalars. It rejects unsupported YAML collections, tags, aliases, duplicate keys and multiline syntax rather than interpreting them approximately.

`tools/graphify.py` imports Markdown into a managed vault. Stable source hashes prevent title collisions. Links resolve against each source's full URL/path and preserve fragments; matching only a basename is deliberately avoided. Code examples and images are not rewritten as text references. Network import is opt-in and checked at every redirect and connection.

## Work structure

For substantial work: define independent slices and their output contracts, execute with the host's authorized tools, challenge load-bearing claims, then synthesize against the user's original goal. Independence is a design aim, not a consequence of assigning different role names; agents on the same model can share errors. Sequential passes share context and must be labeled accordingly.

Use CONFIRMED only with supporting evidence, REFUTED only with counterevidence and UNVERIFIABLE when the required evidence is unavailable. Disagreement is preserved rather than averaged away. Discovery saturation is a heuristic stopping rule, not proof that every possible issue was found. All loops have task/round caps; autopilot defaults to 3 items or 15 minutes with bounded worker calls and host limits.

## Skill improvement and evaluation

`assistant-tuner` audits authorized project/context evidence; `skill-forge` proposes recurring procedures; `skill-eval` tests whether they help. Evaluation needs clean independent contexts, identical task/tool budgets, recorded provider/model/version/input information, randomized labels and rubrics focused on correctness/safety/utility. Process adherence and cost are reported separately. Without independent execution, deliver an unevaluated test plan, not an invented score.

The historical debug-protocol record is not an automated or cross-provider benchmark. Regression tests in this repository validate the deterministic software and structural skill contracts. Live-host acceptance and model quality/cost measurements remain distinct evidence categories.

## Security boundary

Skill instructions influence a model but do not enforce authorization. The deterministic tools protect their local write and import paths; the host owns model execution, tools, approvals, identity, data controls, scheduling and sandboxing. Integrity manifests are not publisher signatures. See SECURITY.md for filesystem trust assumptions, multi-file interruption recovery and limits of static malware-pattern checks.
