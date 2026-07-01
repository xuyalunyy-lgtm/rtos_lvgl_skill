# Release Governance: 20x Efficiency and Major Refactor Gate

Use this file when maintaining the skill itself, preparing a release, auditing
commits, or deciding whether a version bump is patch/minor/major.

## 20x Efficiency Target

The skill's long-term bar is not "more rules"; it is reducing repeated RTOS
engineering work by roughly 20x across review, bring-up, debugging, and module
creation. Prefer improvements in this order:

1. Deterministic automation: checker, generator, registry, sync script, audit.
2. Routing compression: one workflow points to the right small reference/prompt.
3. Reusable artifacts: good/bad fixtures, templates, topology tables, contracts.
4. Review heuristics: concise checklists only when automation is not practical.
5. Knowledge notes: keep as references, not SKILL.md body bloat.

Every non-trivial release must explain which repeated human step became
automated, shortened, or made harder to forget.

## Efficiency Scorecard

Use this scorecard in self-iteration and release notes. A release that does not
move at least one row is probably documentation churn.

| Area | 1x baseline | 20x direction |
|------|-------------|---------------|
| Code review | Human reads all files | `run_review.py` routes default checkers and reports C#.# |
| New module | Rebuild task/queue/lifecycle design each time | Module contract + topology table + lifecycle template |
| Debug | Search logs manually | Symptom table routes to constraints, prompts, and checkers |
| Knowledge reuse | Long prompt copied into context | SKILL routes to one workflow and one small reference |
| Release safety | Manual memory of required checks | `skill_iterate.py --check` and commit audit enforce gates |

## Major Version Refactor Gate

A major version bump means architecture has changed. It must include an overall
refactor pass, not only new constraints. Before releasing `N.0.0`, do all of:

1. Inventory the skill layers: `SKILL.md`, workflows, references, prompts,
   tools, scripts, examples, Lite distribution, install paths.
2. Identify duplicated logic or drift, then centralize it into a registry,
   generator, shared reference, or script.
3. Remove or merge stale routes, prompts, examples, and manual checklist items.
4. Preserve runtime distribution boundaries and Lite sync semantics.
5. Add/adjust automation so the refactor stays true after future releases.
6. Record a "Major refactor" section in CHANGELOG and iteration_log with:
   before/after structure, deleted duplication, new gate, and 20x impact.

Patch and minor versions may still refactor locally, but they do not satisfy the
major gate unless the release notes explicitly document the whole-skill pass.

## Proactive Commit Audit

When the user asks to audit commits or before making a release commit, run:

```bash
python scripts/commit_audit.py --self-test
python scripts/commit_audit.py --max-log 12 --strict-release
git diff --check
python scripts/skill_iterate.py --check
```

Then review the output as findings first:

- version drift between `SKILL.md`, Lite, CHANGELOG, and iteration_log
- major version bump without whole-skill refactor evidence
- tool/checker changes without registry or fixture updates
- prompt/workflow/reference changes not synced to Lite
- product-specific residue in generic runtime paths
- secret or remote credential exposure

Do not create a commit if any strict-release failure remains.
The self-test must prove the audit can detect version drift, missing major
refactor evidence, missing 20x evidence, and product-specific residue.

Lite distribution note: Lite may not include `scripts/` or `tools/`. In Lite,
read this file as policy, then run the commands from the full source repository
or complete the equivalent manual checklist.
