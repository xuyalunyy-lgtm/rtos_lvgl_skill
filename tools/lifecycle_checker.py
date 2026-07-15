#!/usr/bin/env python3
"""
C33 生命周期对称检查器。

检查项:
  C33.1 — init/open/start/enable 必须有 stop/disable/close/deinit
  C33.2 — alloc/create/register/attach 必须有 free/delete/unregister/detach

用法:
    python tools/lifecycle_checker.py <file.c> [file2.c ...]
    python tools/lifecycle_checker.py --dir src/
"""

from __future__ import annotations

import re
from pathlib import Path

from checker_io import make_issue, read_file, run_checker, strip_comments
from sdk_lookup import SdkLookup

lookup = SdkLookup("esp32")

# Lifecycle pairs derived from SDK abstraction layer
_RTOS_PAIR_DEFS = [
    ("TASK_CREATE", "TASK_DELETE", "task create/delete"),
    ("MUTEX_CREATE", "MUTEX_DELETE", "mutex create/delete"),
    ("SEM_CREATE", "SEM_DELETE", "semaphore create/delete"),
    ("QUEUE_CREATE", "QUEUE_DELETE", "queue create/delete"),
    ("TIMER_CREATE", "TIMER_DELETE", "timer create/delete"),
    ("WIFI_EVENT_REGISTER", "WIFI_EVENT_UNREGISTER", "event handler register/unregister"),
]
RTOS_PAIRS = [
    (lookup.get_apis(acq_op)[0], lookup.get_apis(rel_op)[0], desc)
    for acq_op, rel_op, desc in _RTOS_PAIR_DEFS
    if lookup.get_apis(acq_op) and lookup.get_apis(rel_op)
]

# Assignment-based resources are tracked by handle name across every selected
# source file.  Type-level API counts below remain as a fallback for APIs that
# do not return a resource handle (for example event registration).
TRACKED_RESOURCE_PAIRS = [
    *RTOS_PAIRS,
    ("cJSON_Parse", "cJSON_Delete", "cJSON parse/delete"),
    ("cJSON_CreateObject", "cJSON_Delete", "cJSON create/delete"),
    ("cJSON_CreateArray", "cJSON_Delete", "cJSON create/delete"),
    ("fopen", "fclose", "file open/close"),
]


def _source_texts(paths: list[Path]) -> list[tuple[Path, list[str], str]]:
    texts = []
    for path in paths:
        result = read_file(path)
        if result is None:
            continue
        lines, text = result
        texts.append((path, lines, strip_comments(text)))
    return texts


def _resource_handle_issues(texts: list[tuple[Path, list[str], str]]) -> list[dict]:
    """Report resource handles whose matching release is absent project-wide."""
    acquisitions: dict[tuple[str, str], tuple[Path, int, str]] = {}
    releases: set[tuple[str, str]] = set()
    for acquire, release, description in TRACKED_RESOURCE_PAIRS:
        acquire_re = re.compile(rf"\b(?P<handle>[A-Za-z_]\w*)\s*=\s*{re.escape(acquire)}\s*\(")
        release_re = re.compile(rf"\b{re.escape(release)}\s*\(\s*(?P<handle>[A-Za-z_]\w*)\b")
        for path, _lines, text in texts:
            for match in acquire_re.finditer(text):
                handle = match.group("handle")
                acquisitions[(acquire, handle)] = (
                    path,
                    text[:match.start("handle")].count("\n") + 1,
                    description,
                )
            for match in release_re.finditer(text):
                releases.add((acquire, match.group("handle")))

    issues = []
    for key, (path, line, description) in sorted(acquisitions.items(), key=lambda item: (str(item[1][0]), item[1][1])):
        _acquire, handle = key
        if key not in releases:
            issues.append(make_issue(
                path, line, "C33.2", "P0",
                f"resource handle '{handle}' is acquired but no matching release is found across selected files ({description})",
            ))
    return issues


def _type_pair_issues(texts: list[tuple[Path, list[str], str]]) -> list[dict]:
    """Keep a conservative fallback for unassigned SDK resource creation."""
    issues = []
    for acquire, release, desc in RTOS_PAIRS:
        acquire_sites: list[tuple[Path, int]] = []
        release_found = False
        assigned_handle_found = False
        for path, _lines, text in texts:
            for match in re.finditer(rf"\b{re.escape(acquire)}\s*\(", text):
                acquire_sites.append((path, text[:match.start()].count("\n") + 1))
            if re.search(rf"\b[A-Za-z_]\w*\s*=\s*{re.escape(acquire)}\s*\(", text):
                assigned_handle_found = True
            if re.search(rf"\b{re.escape(release)}\s*\(", text):
                release_found = True
        if acquire_sites and not release_found and not assigned_handle_found:
            path, line = acquire_sites[0]
            issues.append(make_issue(
                path, line, "C33.2", "P0",
                f"{len(acquire_sites)}x {acquire} but no {release} across selected files ({desc} asymmetry)",
            ))
    return issues


def _generic_lifecycle_issues(texts: list[tuple[Path, list[str], str]]) -> list[dict]:
    combined = "\n".join(text for _path, _lines, text in texts)
    issues = []
    for path, _lines, text in texts:
        for pattern, replacement, desc in [
            (r'\b(\w+)_init\s*\(', r'\1_deinit', 'init/deinit'),
            (r'\b(\w+)_open\s*\(', r'\1_close', 'open/close'),
            (r'\b(\w+)_start\s*\(', r'\1_stop', 'start/stop'),
        ]:
            for match in re.finditer(pattern, text):
                func_name = match.group(0).split("(")[0].strip()
                release_func = re.sub(pattern, replacement, match.group(0)).split("(")[0].strip()
                if release_func + "(" not in combined:
                    issues.append(make_issue(
                        path, text[:match.start()].count("\n") + 1, "C33.1", "P0",
                        f"{func_name}() called but no {release_func}() across selected files ({desc} asymmetry)",
                    ))
    return issues


def check_paths(paths: list[Path]) -> list[dict]:
    """Check lifecycle symmetry across the complete selected source set."""
    texts = _source_texts(paths)
    return [
        *_type_pair_issues(texts),
        *_resource_handle_issues(texts),
        *_generic_lifecycle_issues(texts),
    ]


def check_file(path: Path) -> list[dict]:
    return check_paths([path])


if __name__ == "__main__":
    raise SystemExit(run_checker(
        check_file, "C33 生命周期对称检查器", ("C33",),
        check_paths_fn=check_paths,
    ))
