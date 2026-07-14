# Workflow: L3 LVGL Page

Use this workflow to turn a confirmed design into a maintainable LVGL page in
the target firmware project. This skill does not provide a bundled code
generator or simulator.

## Inputs

- Design screenshot and target display dimensions
- LVGL version and target-project build command
- Cut assets, fonts, text, page states, and interaction decisions

## Delivery

- Page C/H files, assets, and build-system entries required by the target
  project
- A concise record of display assumptions, asset ownership, and interaction
  behavior
- Build or hardware verification evidence from the target project

## Process

1. Confirm coordinate space, asset roles, fonts, page states, and runtime
   ownership before coding.
2. Prefer Flex or Grid for adaptive groups. Use fixed coordinates only for
   intentional design reconstruction and document the reason beside the code.
3. Keep LVGL calls in the GUI context. Post background-task updates through the
   project's existing queue, presenter, or async mechanism.
4. Use assets for complex artwork; use LVGL widgets for dynamic labels,
   controls, and indicators.
5. Build in the target project, then verify on its simulator or device. Treat
   a browser mockup as a layout aid, not visual proof.

## Completion checks

- All assets and fonts resolve through the target build.
- The page compiles for the selected LVGL version.
- No background task mutates an LVGL object directly.
- Display size, touch behavior, and state transitions are verified.
