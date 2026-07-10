# log symptom allowlist governance

## Allowlist Change Approval Path

1. Before submitting changes in `references/log_symptom_route_conflict_allowlist.json`, describe in the PR description:
   - Source of the `fixture` or `route_id` for the changed entry
   - Reproduction evidence for the corresponding conflict (logs/routes or reproducible scripts)
   - Planned cleanup schedule and expiration date
2. Verify that rules will not be amplified to unexpected scope via `python scripts/check_log_symptom_quality_gate.py --strict`.
3. List separately in code review:
   - This is an “add/remove allowlist entry” change
   - The change is a one-time exemption with reclaim conditions attached

## Quick Governance Rules

- `scripts/check_log_symptom_quality_gate.py` records the `md5 + mtime` of the allowlist and policy on each run.
- When compared with `HEAD`, it returns a failure if only formatting or semantics are unchanged (semantic noop rejection), to prevent “empty changes” from entering the repository.
- If the `allowlist` or `policy` files are modified, it is recommended to update the above audit records in the review (reason, archival time, Owner).