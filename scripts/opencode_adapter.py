#!/usr/bin/env python3
"""Thin OpenCode plugin adapter for Agent Thought Map generic events."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from thought_map_core import append_event, is_trace_active, redact_text, update_latest


def data_root(args: argparse.Namespace) -> Path:
    raw = getattr(args, "data_dir", None) or os.environ.get("AGENT_THOUGHT_MAP_DATA")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.cwd() / ".agent-thought-map-data").resolve()


def read_native_event() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw.lstrip("\ufeff"))
    except json.JSONDecodeError:
        return {"raw_input": redact_text(raw, limit=300)}
    return payload if isinstance(payload, dict) else {"raw_input": payload}


def nested_get(payload: dict[str, Any], paths: list[tuple[str, ...]]) -> Any:
    for path in paths:
        value: Any = payload
        for key in path:
            if not isinstance(value, dict) or key not in value:
                value = None
                break
            value = value[key]
        if value not in (None, ""):
            return value
    return None


def extract_tool_name(payload: dict[str, Any]) -> str:
    value = nested_get(payload, [("tool",), ("tool_name",), ("name",)])
    return redact_text(str(value), limit=80) if value is not None else ""


def extract_target(payload: dict[str, Any]) -> str:
    value = nested_get(
        payload,
        [
            ("command",),
            ("filePath",),
            ("file_path",),
            ("args", "command"),
            ("args", "filePath"),
            ("args", "file_path"),
        ],
    )
    if value is not None:
        return redact_text(str(value), limit=220)
    title = nested_get(payload, [("title",)])
    return redact_text(str(title), limit=220) if title is not None else ""


def extract_status(payload: dict[str, Any], hook_event: str) -> str:
    if hook_event in {"session.error", "tool.execute.after"}:
        for key in ("status", "outcome"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                lower = value.lower()
                if lower in {"ok", "success", "succeeded", "passed"}:
                    return "ok"
                if lower in {"failed", "failure", "error", "denied"}:
                    return "failed"
                if lower in {"blocked", "cancelled", "canceled"}:
                    return "blocked"
        success = nested_get(payload, [("success",), ("metadata", "success")])
        if isinstance(success, bool):
            return "ok" if success else "failed"
        if hook_event == "session.error":
            return "failed"
    return "unknown"


def infer_kind(hook_event: str, tool_name: str, target: str, status: str) -> str:
    if hook_event in {"permission.asked", "permission.replied"}:
        return "decision"
    text = f"{tool_name} {target}".lower()
    if any(word in text for word in ("pytest", "test", "lint", "typecheck", "build", "validate", "check")):
        return "validation"
    if any(word in text for word in ("edit", "write", "patch", "mv ", "cp ", "chmod")):
        return "action"
    if any(
        word in text
        for word in ("rg ", "grep", "glob", "read", "sed ", "find ", "ls ", "cat ", "git status", "git diff", "pwd", "bash")
    ):
        return "investigation"
    if status == "failed":
        return "retry"
    if hook_event in {"session.created", "session.idle", "session.status"}:
        return "discovery"
    return "discovery"


def title_for_event(hook_event: str, kind: str, actor: str, target: str) -> str:
    if hook_event == "session.created":
        return "Session started"
    if hook_event == "session.idle":
        return "Session idle"
    if hook_event == "session.error":
        return "Session error"
    if hook_event in {"permission.asked", "permission.replied"}:
        return f"Permission event for {actor or 'tool'}"
    if target:
        titles = {
            "investigation": "Inspect project state",
            "validation": "Run validation check",
            "action": "Apply implementation action",
            "retry": "Handle failed attempt",
        }
        return titles.get(kind, f"Observe {actor or 'tool'}")
    return f"Observe {hook_event or 'OpenCode event'}"


def normalize_event(payload: dict[str, Any]) -> dict[str, Any]:
    hook_event = str(payload.get("event") or payload.get("hook_event_name") or "unknown")
    trace_id = str(
        payload.get("sessionID")
        or payload.get("session_id")
        or os.environ.get("AGENT_THOUGHT_MAP_TRACE_ID")
        or "manual"
    )
    actor = extract_tool_name(payload)
    target = extract_target(payload)
    status = extract_status(payload, hook_event)
    kind = infer_kind(hook_event, actor, target, status)
    native_ref = {
        "runtime": "opencode",
        "hook_event": hook_event,
    }
    if payload.get("callID"):
        native_ref["call_id"] = str(payload["callID"])

    summary_parts = [hook_event]
    if actor:
        summary_parts.append(f"actor={actor}")
    if target:
        summary_parts.append(f"target={target}")
    if status != "unknown":
        summary_parts.append(f"status={status}")

    return {
        "trace_id": trace_id,
        "kind": kind,
        "title": title_for_event(hook_event, kind, actor, target),
        "summary": "; ".join(summary_parts),
        "status": status,
        "source": "opencode-adapter",
        "actor": actor,
        "target": target,
        "tags": ["opencode", hook_event],
        "native_ref": native_ref,
    }


def command_collect(args: argparse.Namespace) -> int:
    root = data_root(args)
    native_event = read_native_event()
    generic_event = normalize_event(native_event)
    trace_id = str(generic_event["trace_id"])
    update_latest(root, trace_id)
    if is_trace_active(root, trace_id):
        append_event(root, generic_event)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect OpenCode plugin events as generic Agent Thought Map events.")
    parser.add_argument("--data-dir", help="Trace data directory. Defaults to AGENT_THOUGHT_MAP_DATA.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect", help="Read one OpenCode event from stdin and append a generic event.")
    collect.set_defaults(func=command_collect)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
