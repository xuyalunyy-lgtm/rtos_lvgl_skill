# Workflow Acceptance Criteria

This reference defines completion checks for the workflows retained in this
skill. It does not require a bundled service, generator, or simulator.

## Code Review (`l2_code_review`)

- Findings identify the affected file or subsystem, risk, and verification.
- Critical safety, ownership, and lifecycle issues have a concrete next step.

## Project Review (`l2_project_review`)

- Repository structure, configuration, build entry points, and security
  hygiene were inspected within the requested scope.
- Results distinguish blocking risks from follow-up improvements.

## Memory Analysis (`l2_memory_analysis`)

- Allocation ownership, peak usage, fragmentation risk, and release paths are
  documented with evidence.

## Crash Debug (`debug_crash`)

- The report contains a reproducible symptom, evidence-backed hypotheses, and
  a minimal verification plan.

## Hardware/Software Co-debug (`hw_sw_cocodebug`)

- Pin, bus, power, interrupt, and timing ownership are recorded before a
  proposed firmware change.

## Bring-up (`l3_bring_up`)

- Boot sequence, peripheral checks, watchdog behavior, and recovery evidence
  are verified on the target board or equivalent environment.

## New Module (`l3_new_module`)

- Public contract, lifecycle, ownership, error handling, and task topology are
  defined and built in the target project.

## SDK Trimming (`l3_sdk_trim`)

- Every removed component is unused by configuration and initialization paths;
  the target build remains successful.
