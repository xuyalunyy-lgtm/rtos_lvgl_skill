"""SDK-map-only YAML subset loader, stdlib only.

This module is intentionally scoped to the YAML shape used by
references/sdk_abstraction.yaml and platforms/*_sdk_map.yaml. It is not a
general YAML parser and should not grow into one; unsupported YAML features are
rejected at load time instead of being partially interpreted.

Supported project subset:
  - Nested mappings (indent-based)
  - Block sequences (- item) and flow sequences (["a", "b"])
  - Scalars: str (quoted/unquoted), int, float, bool (true/false), null
  - Comments (# ...)
  - Folded (>) and literal (|) block scalars

Explicitly rejected: anchors/aliases (&/*), merge keys (<<), tags (!!),
flow mappings ({...}), complex keys, multi-document (---), directives.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TextIO


SUPPORTED_SCOPE = "references/sdk_abstraction.yaml and platforms/*_sdk_map.yaml"


class UnsupportedYamlFeature(ValueError):
    """Raised when input uses YAML outside the project SDK-map subset."""


_FLOW_MAPPING_RE = re.compile(r"(^|[:\[,]\s*)\{[^}]*:[^}]*\}")
_ANCHOR_ALIAS_RE = re.compile(r"(^|[\s\[,])([&*][A-Za-z0-9_-]+)")
_TAG_RE = re.compile(r"(^|[\s\[,])![A-Za-z!][^\s,\]]*")


# ── Scalar parsing ──────────────────────────────────────────────

_BOOL_TRUE = {"true", "True", "TRUE", "yes", "Yes", "YES", "on", "On", "ON"}
_BOOL_FALSE = {"false", "False", "FALSE", "no", "No", "NO", "off", "Off", "OFF"}
_NULL_TOKENS = {"null", "Null", "NULL", "~"}

_INT_RE = re.compile(r"^[-+]?(0|[1-9][0-9]*)$")
_FLOAT_RE = re.compile(r"^[-+]?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?")


def _parse_scalar(text: str) -> Any:
    """Parse a YAML scalar value into a Python object."""
    text = text.strip()
    if not text:
        return ""

    # Quoted strings
    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        return _unescape_quoted(text[1:-1], text[0])

    # Boolean
    if text in _BOOL_TRUE:
        return True
    if text in _BOOL_FALSE:
        return False

    # Null
    if text in _NULL_TOKENS:
        return None

    # Integer
    if _INT_RE.match(text):
        try:
            return int(text)
        except ValueError:
            pass

    # Float
    if _FLOAT_RE.match(text):
        try:
            return float(text)
        except ValueError:
            pass

    # Unquoted string
    return text


def _unescape_quoted(text: str, quote: str) -> str:
    """Minimal escape handling for quoted strings."""
    if quote == "'":
        return text.replace("''", "'")
    # Double-quoted: handle common escapes
    text = text.replace('\\"', '"')
    text = text.replace("\\n", "\n")
    text = text.replace("\\t", "\t")
    text = text.replace("\\\\", "\\")
    return text


# ── Flow sequence parsing ───────────────────────────────────────

def _parse_flow_seq(text: str) -> list[Any]:
    """Parse a flow sequence like ["a", "b", "c"]."""
    text = text.strip()
    if not text.startswith("[") or not text.endswith("]"):
        raise ValueError(f"invalid flow sequence: {text!r}")
    inner = text[1:-1].strip()
    if not inner:
        return []
    # Split by comma, respecting quoted strings
    items: list[str] = []
    current = ""
    in_quote: str | None = None
    depth = 0
    for ch in inner:
        if in_quote:
            current += ch
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
            current += ch
        elif ch == "[":
            depth += 1
            current += ch
        elif ch == "]" and depth > 0:
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            items.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        items.append(current.strip())
    return [_parse_scalar(item) for item in items]


# ── Line-level helpers ──────────────────────────────────────────

def _indent_level(line: str) -> int:
    """Return the number of leading spaces."""
    return len(line) - len(line.lstrip(" "))


def _strip_comment(line: str) -> str:
    """Strip trailing comment, respecting quoted strings."""
    in_quote: str | None = None
    for i, ch in enumerate(line):
        if in_quote:
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
        elif ch == "#" and in_quote is None:
            return line[:i].rstrip()
    return line.rstrip()


def _is_blank_or_comment(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def _mask_quoted_segments(text: str) -> str:
    """Replace quoted content with spaces so feature checks see only syntax."""
    out: list[str] = []
    in_quote: str | None = None
    escaped = False
    for ch in text:
        if in_quote:
            out.append(" ")
            if escaped:
                escaped = False
            elif in_quote == '"' and ch == "\\":
                escaped = True
            elif ch == in_quote:
                in_quote = None
            continue
        if ch in ('"', "'"):
            in_quote = ch
            out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def _reject_unsupported_features(lines: list[str]) -> None:
    """Reject YAML features outside the SDK-map subset before parsing."""
    for line_no, line in enumerate(lines, start=1):
        stripped = _strip_comment(line).strip()
        if not stripped:
            continue
        visible = _mask_quoted_segments(stripped)
        if stripped in {"---", "..."}:
            raise UnsupportedYamlFeature(f"line {line_no}: multi-document YAML is not supported")
        if stripped.startswith("%"):
            raise UnsupportedYamlFeature(f"line {line_no}: YAML directives are not supported")
        if "\t" in line[: _indent_level(line)]:
            raise UnsupportedYamlFeature(f"line {line_no}: tab indentation is not supported")
        if re.search(r"(^|[\s\[,])<<\s*:", visible):
            raise UnsupportedYamlFeature(f"line {line_no}: merge keys are not supported")
        if _FLOW_MAPPING_RE.search(visible):
            raise UnsupportedYamlFeature(f"line {line_no}: flow mappings are not supported")
        if _ANCHOR_ALIAS_RE.search(visible):
            raise UnsupportedYamlFeature(f"line {line_no}: anchors and aliases are not supported")
        if _TAG_RE.search(visible):
            raise UnsupportedYamlFeature(f"line {line_no}: YAML tags are not supported")


# ── Block scalar collection ─────────────────────────────────────

def _collect_block_scalar(lines: list[str], start: int, indent: int, style: str) -> tuple[str, int]:
    """Collect a block scalar (>|) and return (content, next_line_index)."""
    result: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if _is_blank_or_comment(line):
            if not line.strip():
                result.append("")
            i += 1
            continue
        line_indent = _indent_level(line)
        if line_indent <= indent:
            break
        result.append(line[indent:])
        i += 1
    # Remove trailing blank lines
    while result and not result[-1].strip():
        result.pop()
    if style == ">":
        # Folded: join lines with spaces, preserve blank-line paragraph breaks
        paragraphs: list[str] = []
        current_para: list[str] = []
        for rline in result:
            if rline.strip():
                current_para.append(rline.strip())
            else:
                if current_para:
                    paragraphs.append(" ".join(current_para))
                    current_para = []
        if current_para:
            paragraphs.append(" ".join(current_para))
        return "\n".join(paragraphs), i
    else:
        # Literal
        return "\n".join(result), i


# ── Main recursive parser ───────────────────────────────────────

def _parse_block(lines: list[str], start: int, base_indent: int) -> tuple[Any, int]:
    """Parse a block mapping or sequence starting at base_indent.

    Returns (parsed_value, next_line_index).
    """
    # Peek at first non-blank line to determine type
    i = start
    while i < len(lines) and _is_blank_or_comment(lines[i]):
        i += 1
    if i >= len(lines):
        return None, i

    first = lines[i]
    first_indent = _indent_level(first)
    first_stripped = _strip_comment(first).strip()

    # Is this a block sequence?
    if first_stripped.startswith("- ") or first_stripped == "-":
        return _parse_block_sequence(lines, i, base_indent)

    # Otherwise it's a mapping
    return _parse_block_mapping(lines, i, base_indent)


def _parse_block_sequence(lines: list[str], start: int, base_indent: int) -> tuple[list[Any], int]:
    """Parse a block sequence (- item)."""
    result: list[Any] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if _is_blank_or_comment(line):
            i += 1
            continue
        indent = _indent_level(line)
        if indent < base_indent:
            break
        if indent > base_indent:
            break  # shouldn't happen in well-formed YAML
        stripped = _strip_comment(line).strip()
        if not stripped.startswith("- "):
            break
        # Get the value after "- "
        value_part = stripped[2:]
        if not value_part:
            # Value is a nested block on the next line(s)
            child_indent = _find_child_indent(lines, i + 1, base_indent)
            if child_indent is not None:
                val, i = _parse_block(lines, i + 1, child_indent)
            else:
                val = None
                i += 1
        elif ":" in value_part and not value_part.startswith('"') and not value_part.startswith("'"):
            # Inline mapping item: "- key: value" or "- key:\n  nested"
            key, _, val_str = value_part.partition(":")
            key = key.strip()
            val_str = val_str.strip()
            if val_str:
                # Value on same line as key
                if val_str.startswith("[") and val_str.endswith("]"):
                    val = _parse_flow_seq(val_str)
                else:
                    val = _parse_scalar(val_str)
                result.append({key: val})
                i += 1
            else:
                # Nested block under "- key:"
                child_indent = _find_child_indent(lines, i + 1, base_indent + 2)
                if child_indent is not None:
                    nested, i = _parse_block(lines, i + 1, child_indent)
                else:
                    nested = None
                    i += 1
                result.append({key: nested})
        else:
            # Simple scalar value
            if value_part.startswith("[") and value_part.endswith("]"):
                result.append(_parse_flow_seq(value_part))
            else:
                result.append(_parse_scalar(value_part))
            i += 1
    return result, i


def _parse_block_mapping(lines: list[str], start: int, base_indent: int) -> tuple[dict[str, Any], int]:
    """Parse a block mapping (key: value)."""
    result: dict[str, Any] = {}
    i = start
    while i < len(lines):
        line = lines[i]
        if _is_blank_or_comment(line):
            i += 1
            continue
        indent = _indent_level(line)
        if indent < base_indent:
            break
        if indent > base_indent:
            break  # shouldn't happen
        stripped = _strip_comment(line).strip()
        if not stripped:
            i += 1
            continue

        # Parse key: value
        key, _, val_str = stripped.partition(":")
        key = key.strip()
        val_str = val_str.strip()

        # Handle quoted keys
        if (key.startswith('"') and key.endswith('"')) or \
           (key.startswith("'") and key.endswith("'")):
            key = key[1:-1]

        if not val_str:
            # Value is on the next line(s)
            child_indent = _find_child_indent(lines, i + 1, indent)
            if child_indent is not None:
                val, i = _parse_block(lines, i + 1, child_indent)
            else:
                val = None
                i += 1
        elif val_str in (">", "|", ">-", "|-", ">", "|"):
            # Block scalar
            block_indent = _find_child_indent(lines, i + 1, indent)
            if block_indent is None:
                block_indent = indent + 2
            style = ">" if val_str.startswith(">") else "|"
            val, i = _collect_block_scalar(lines, i + 1, indent, style)
        elif val_str.startswith("[") and val_str.endswith("]"):
            val = _parse_flow_seq(val_str)
            i += 1
        elif val_str.startswith("[") and "]" not in val_str:
            # Multi-line flow sequence: accumulate until closing bracket
            acc = val_str
            i += 1
            while i < len(lines):
                next_line = lines[i]
                if _is_blank_or_comment(next_line):
                    i += 1
                    continue
                acc += " " + _strip_comment(next_line).strip()
                i += 1
                if "]" in acc:
                    break
            val = _parse_flow_seq(acc)
        else:
            val = _parse_scalar(val_str)
            i += 1

        result[key] = val
    return result, i


def _find_child_indent(lines: list[str], start: int, parent_indent: int) -> int | None:
    """Find the indentation of the next non-blank, non-comment line."""
    i = start
    while i < len(lines):
        line = lines[i]
        if _is_blank_or_comment(line):
            i += 1
            continue
        indent = _indent_level(line)
        if indent > parent_indent:
            return indent
        return None  # Same or less indent → no child block
    return None


# ── Public API ──────────────────────────────────────────────────

def safe_load(stream: TextIO | str) -> Any:
    """Parse the project SDK-map YAML subset from a file-like object or string.

    This is intentionally not a general-purpose yaml.safe_load replacement.
    It accepts only the subset used by SUPPORTED_SCOPE.
    """
    if isinstance(stream, str):
        text = stream
    else:
        text = stream.read()

    # Strip UTF-8 BOM if present
    if text.startswith("﻿"):
        text = text[1:]

    lines = text.split("\n")
    _reject_unsupported_features(lines)
    result, _ = _parse_block(lines, 0, 0)
    return result


def safe_load_str(text: str) -> Any:
    """Parse SDK-map subset YAML from a string. Convenience alias."""
    return safe_load(text)


# ── CLI self-test ───────────────────────────────────────────────

def _self_test() -> int:
    """Validate against the project's actual YAML files."""
    root = Path(__file__).resolve().parent.parent

    unsupported_samples = {
        "flow mapping": "mappings: {SEM_TAKE: {apis: [xSemaphoreTake]}}\n",
        "anchor": "base: &base\n  apis: [xSemaphoreTake]\n",
        "alias": "copy: *base\n",
        "merge key": "mapping:\n  <<: *base\n",
        "tag": "value: !!str 1\n",
        "multi-document": "---\nvalue: 1\n",
    }
    for feature, sample in unsupported_samples.items():
        try:
            safe_load(sample)
        except UnsupportedYamlFeature:
            pass
        else:
            raise AssertionError(f"unsupported YAML feature was accepted: {feature}")
    print("OK: unsupported general YAML features are rejected")

    # Test 1: sdk_abstraction.yaml
    abstr_path = root / "references" / "sdk_abstraction.yaml"
    if abstr_path.exists():
        with open(abstr_path, "r", encoding="utf-8") as f:
            data = safe_load(f)
        assert isinstance(data, dict), "sdk_abstraction.yaml should parse as dict"
        assert "version" in data, "missing 'version' key"
        assert "rtos_semaphore" in data, "missing 'rtos_semaphore' key"
        assert "SEM_TAKE" in data["rtos_semaphore"], "missing SEM_TAKE"
        assert data["rtos_semaphore"]["SEM_TAKE"]["checker_hints"] == [
            "must_have_timeout", "isr_forbidden", "hot_path_forbidden"
        ], f"checker_hints mismatch: {data['rtos_semaphore']['SEM_TAKE']['checker_hints']}"
        print(f"OK: sdk_abstraction.yaml ({len(data)} top-level keys)")

    # Test 2: platform sdk maps
    for yaml_file in sorted((root / "platforms").glob("*_sdk_map.yaml")):
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = safe_load(f)
        if yaml_file.name == "freertos_sdk_map.yaml":
            # This file is a simple list, not a mapping
            assert isinstance(data, list), f"{yaml_file.name} should parse as list"
            print(f"OK: {yaml_file.name} ({len(data)} items, list)")
        else:
            assert isinstance(data, dict), f"{yaml_file.name} should parse as dict"
            assert "mappings" in data, f"missing 'mappings' in {yaml_file.name}"
            mappings = data["mappings"]
            assert "SEM_TAKE" in mappings, f"missing SEM_TAKE in {yaml_file.name}"
            print(f"OK: {yaml_file.name} ({len(mappings)} mappings)")

    print("minimal_yaml self-test passed")
    return 0


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    else:
        print("Usage: python minimal_yaml.py --self-test  # SDK-map subset only")
        raise SystemExit(1)
