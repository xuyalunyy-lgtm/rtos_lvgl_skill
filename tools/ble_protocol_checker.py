#!/usr/bin/env python3
"""C46 BLE protocol contract checker (ESP-IDF/NimBLE/Zephyr heuristics)."""
from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker, strip_comments

BLE_HINT_RE = re.compile(r"\b(?:ble|gatt|gap|nimble|bt_)\w*", re.IGNORECASE)
BLE_INIT_RE = re.compile(r"\b(?:bt_enable|nimble_port_init|esp_bluedroid_init|esp_ble_gatts_app_register|ble_svc_gap_init)\s*\(", re.IGNORECASE)
BLE_STOP_RE = re.compile(r"\b(?:bt_disable|nimble_port_stop|nimble_port_deinit|esp_bluedroid_deinit|ble_gap_adv_stop)\s*\(", re.IGNORECASE)
BLE_CONNECT_RE = re.compile(r"\b(?:bt_conn_le_create|ble_gap_connect|esp_ble_gap_start_advertising|ble_gap_adv_start)\s*\(", re.IGNORECASE)
STATE_RE = re.compile(r"\b\w*(?:ble|gatt|gap|bt)\w*(?:state|conn)\w*\b|\benum\s+\w*(?:ble|gatt|gap|conn)\w*", re.IGNORECASE)
STATE_WORDS = ("idle", "connecting", "connected", "disconnecting")
PAIRING_RE = re.compile(r"\b(?:pair|auth|passkey|security)\w*\s*\(", re.IGNORECASE)
SECURITY_RE = re.compile(r"\b(?:encrypt|bond|security|auth_mode|mitm)\w*", re.IGNORECASE)
MTU_RE = re.compile(r"\b(?:mtu|ATT_MTU)\b", re.IGNORECASE)
MTU_NEGOTIATION_RE = re.compile(r"\b(?:exchange_mtu|mtu_exchange|negotiate_mtu|ble_gattc_exchange_mtu)\b", re.IGNORECASE)


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []
    _lines, raw = result
    code = strip_comments(raw)
    lower = code.lower()
    if not BLE_HINT_RE.search(code):
        return []
    issues: list[dict] = []
    init = BLE_INIT_RE.search(code)
    if init and not STATE_RE.search(code):
        issues.append(make_issue(path, code[:init.start()].count("\n") + 1, "C46.1", "P1", "BLE init has no explicit state owner/state machine"))
    if init and not BLE_STOP_RE.search(code):
        issues.append(make_issue(path, code[:init.start()].count("\n") + 1, "C46.1", "P1", "BLE init has no visible stop/deinit/rollback path"))
    connect = BLE_CONNECT_RE.search(code)
    if connect and not all(word in lower for word in STATE_WORDS):
        issues.append(make_issue(path, code[:connect.start()].count("\n") + 1, "C46.4", "P1", "BLE connection flow lacks idle/connecting/connected/disconnecting state coverage"))
    pairing = PAIRING_RE.search(code)
    if pairing and not SECURITY_RE.search(code[pairing.end():]):
        issues.append(make_issue(path, code[:pairing.start()].count("\n") + 1, "C46.5", "P2", "BLE pairing/auth path lacks visible encryption or bond lifecycle"))
    if MTU_RE.search(code) and not MTU_NEGOTIATION_RE.search(code):
        issues.append(make_issue(path, 1, "C46.6", "P1", "BLE MTU is referenced without visible capability negotiation/exchange"))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C46 BLE protocol checker", ("C46",)))
