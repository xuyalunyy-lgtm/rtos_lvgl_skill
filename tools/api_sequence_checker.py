#!/usr/bin/env python3
"""C20/C23 API sequence checker for WiFi/MQTT and camera bring-up.

Only calls in the same function are compared.  WiFi and MQTT commonly cross
event callbacks, so absence of an earlier call is not treated as an error.
"""
from __future__ import annotations

import re
from pathlib import Path

from checker_io import extract_functions, make_issue, read_file, run_checker, strip_comments


def _call_pattern(names: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(re.escape(name) for name in names) + r")\s*\(")


WIFI_CONNECT_RE = _call_pattern(("esp_wifi_connect", "wifi_connect", "wifi_start_connect"))
MQTT_CONNECT_RE = _call_pattern(("esp_mqtt_client_start", "esp_mqtt_client_reconnect", "mqtt_connect", "mqtt_client_connect"))
MQTT_SUBSCRIBE_RE = _call_pattern(("esp_mqtt_client_subscribe", "mqtt_subscribe", "mqtt_client_subscribe"))
CAMERA_INIT_RE = _call_pattern(("esp_camera_init", "camera_init", "camera_open"))
CAMERA_START_RE = _call_pattern(("esp_camera_fb_get", "camera_start", "camera_capture_start"))


def _first(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(text)
    return match.start() if match else None


def check_file(path: Path) -> list[dict]:
    result = read_file(path)
    if result is None:
        return []
    _lines, text = result
    code = strip_comments(text)
    issues: list[dict] = []
    for function in extract_functions(code):
        body = function.body
        wifi = _first(WIFI_CONNECT_RE, body)
        mqtt = _first(MQTT_CONNECT_RE, body)
        subscribe = _first(MQTT_SUBSCRIBE_RE, body)
        camera_init = _first(CAMERA_INIT_RE, body)
        camera_start = _first(CAMERA_START_RE, body)

        if wifi is not None and mqtt is not None and mqtt < wifi:
            issues.append(make_issue(
                path, function.line, "C20.6", "P0",
                f"{function.name}() starts MQTT before WiFi connect; wait for the IP-ready path",
            ))
        if mqtt is not None and subscribe is not None and subscribe < mqtt:
            issues.append(make_issue(
                path, function.line, "C20.6", "P0",
                f"{function.name}() subscribes before MQTT connect/start",
            ))
        if camera_init is not None and camera_start is not None and camera_start < camera_init:
            issues.append(make_issue(
                path, function.line, "C23.7", "P0",
                f"{function.name}() starts/captures camera before camera init",
            ))
    return issues


if __name__ == "__main__":
    raise SystemExit(run_checker(check_file, "C20/C23 API sequence checker", ("C20", "C23")))
