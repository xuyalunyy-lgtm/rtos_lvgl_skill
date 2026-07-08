# Constraint: Bluetooth Protocol Adaptation

> Strictness: BLE protocol adaptation is high strictness.
> Must pass C46 constraints in `references/constraint_index.md` before code change.

## Scope

- Constraint ID: C46.1-C46.8
- Platform: ESP32 / JL / BK / STM32 / Zephyr
- Purpose: define API contract, state transitions, parameter policy and error handling for BLE.

### Severity

| Level | Meaning | Handling |
|-------|---------|----------|
| P0 | Critical crash / unusable path | block merge until fixed |
| P1 | High probability production issue | fix in this iteration or add a risk record |
| P2 | Maintainability / consistency gap | fix as priority in next cycle |

## C46 -- BLE Protocol Verification

| ID | Constraint | Severity | Validation |
|----|------------|----------|-----------|
| C46.1 | BLE init/close must follow explicit state machine (`init -> configure -> start -> stop -> deinit`) and rollback path on failure | P1 | Manual review + log trace |
| C46.2 | ADV/reconnect/scan params (interval, timeout, window) must come from profile or board config, no hard-coded magic values | P1 | Manual + fixture check |
| C46.3 | GATT service, UUID, characteristic definitions must match docs and route mapping exactly; any change needs doc update first | P1 | Manual review |
| C46.4 | State machine must cover `idle/connecting/connected/disconnecting` and define timeout recovery | P1 | Manual + event replay |
| C46.5 | Pairing/auth/encryption/bond lifecycle must be explicit and release contexts on failure | P2 | Manual review |
| C46.6 | MTU and fragment settings must negotiate by capability and support fallback | P1 | Manual + compatibility test |
| C46.7 | Error classification must distinguish recoverable/fatal and map to retry/backoff/disable/alert actions | P1 | Review + log schema check |
| C46.8 | Platform capability mapping must cover ESP32/JL/BK/STM32/Zephyr boundaries and avoid cross-platform misuse | P1 | Capability matrix review |

### Platform alignment checklist

- ESP32: isolate BLE and Wi-Fi lifetime, deterministic init/stop order.
- JL: BLE enable and provisioning profile switches must be kept consistent.
- BK: ensure BLE config and profile lifecycle share the same transition boundaries.
- STM32: wrap scan/adv/connect lifecycle to keep callbacks and task state in sync.
- Zephyr: keep `prj.conf` and DTS capabilities synchronized with code branches.

### Acceptance

1. Any service/UUID/error-code/MTU change must be reflected in this document and reviewed before implementation.
2. At least four regressions are required: init failure, reconnect storm, pairing failure, MTU fallback.
3. Logs must expose recoverable vs fatal classification and selected recovery action.

### Symptom map

| Symptom | Possible constraints |
|---------|----------------------|
| Connection fails | C46.1/C46.4 |
| Reconnect storm | C46.2/C46.7 |
| Pairing exception | C46.5 |
| Compatibility crash | C46.3/C46.6/C46.8 |
