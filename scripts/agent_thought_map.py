#!/usr/bin/env python3
"""Harness-agnostic CLI for Agent Thought Map generic events."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from thought_map_core import (
    DEFAULT_MAX_NODES,
    VALID_KINDS,
    VALID_STATUSES,
    activate_trace,
    append_event,
    events_path,
    import_events,
    latest_trace_id,
    make_event,
    normalize_event,
    read_jsonl,
    render_trace,
    update_latest,
)


def data_root(args: argparse.Namespace) -> Path:
    raw = getattr(args, "data_dir", None) or os.environ.get("AGENT_THOUGHT_MAP_DATA")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.cwd() / ".agent-thought-map-data").resolve()


def resolve_trace_id(root: Path, args: argparse.Namespace) -> str:
    explicit = getattr(args, "trace_id", None)
    if explicit:
        return explicit
    return latest_trace_id(root) or "manual"


def command_checkpoint(args: argparse.Namespace) -> int:
    root = data_root(args)
    trace_id = resolve_trace_id(root, args)
    event = make_event(
        trace_id=trace_id,
        kind=args.kind,
        title=args.title,
        summary=args.summary or args.title,
        status=args.status,
        source="manual",
        actor=args.actor,
        target=args.target,
        tags=args.tag,
        parent_id=args.parent_id,
    )
    activate_trace(root, trace_id)
    append_event(root, event)
    update_latest(root, trace_id)
    print(str(events_path(root, trace_id)))
    return 0


def command_import_jsonl(args: argparse.Namespace) -> int:
    root = data_root(args)
    trace_id = resolve_trace_id(root, args)
    events = read_jsonl(Path(args.input).expanduser().resolve())
    count = import_events(root, trace_id, [normalize_event(event, default_trace_id=trace_id) for event in events])
    print(f"imported {count} events into {events_path(root, trace_id)}")
    return 0


def command_render(args: argparse.Namespace) -> int:
    root = data_root(args)
    trace_id = resolve_trace_id(root, args)
    outputs = render_trace(root, trace_id, max_nodes=args.max_nodes)
    print(outputs["latest_md"])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import generic Agent Thought Map events and render a graph.")
    parser.add_argument("--data-dir", help="Trace data directory. Defaults to AGENT_THOUGHT_MAP_DATA, then .agent-thought-map-data.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    checkpoint = subparsers.add_parser("checkpoint", help="Append an explicit generic checkpoint event.")
    checkpoint.add_argument("--trace-id", help="Trace id. Defaults to latest trace or manual.")
    checkpoint.add_argument("--kind", required=True, choices=sorted(VALID_KINDS))
    checkpoint.add_argument("--title", required=True)
    checkpoint.add_argument("--summary", default="")
    checkpoint.add_argument("--status", choices=sorted(VALID_STATUSES), default="unknown")
    checkpoint.add_argument("--actor", default="")
    checkpoint.add_argument("--target", default="")
    checkpoint.add_argument("--tag", action="append", default=[])
    checkpoint.add_argument("--parent-id", default="")
    checkpoint.set_defaults(func=command_checkpoint)

    importer = subparsers.add_parser("import-jsonl", help="Import generic JSONL events.")
    importer.add_argument("--trace-id", help="Trace id. Defaults to latest trace or manual.")
    importer.add_argument("--input", required=True, help="Path to a JSONL file containing generic events.")
    importer.set_defaults(func=command_import_jsonl)

    render = subparsers.add_parser("render", help="Render the latest Mermaid graph.")
    render.add_argument("--trace-id", help="Trace id. Defaults to latest trace or manual.")
    render.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    render.set_defaults(func=command_render)

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
