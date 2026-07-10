## Step 3 — Code Generation and Implementation (Lite)

**Default:** [core_rules.md](../references/core_rules.md) **Autonomous Implementation Mode** — Hand-write skeleton according to scene prompt, write directly into user project.

**Lite Limitations:** No `examples/`, `tools/`, `mvp_codegen`, `run_review`; follow [lite_manual_checklist.md](../references/lite_manual_checklist.md) to complete manual review.

## Step 4 — Compilation Closed Loop (Required)

Execute compilation per `platforms/xxx.md`; fix errors and recompile on failure until **0 error**.

## Step 5 — Manual Verification (Lite)

Execute [lite_manual_checklist.md](../references/lite_manual_checklist.md), and manually verify C1/C2/C3/C4 constraints against loaded prompts.
