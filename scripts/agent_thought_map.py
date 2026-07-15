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
    append_cot_event,
    append_event,
    cot_events_path,
    events_path,
    import_events,
    latest_trace_id,
    make_event,
    normalize_event,
    read_jsonl,
    render_cot_trace,
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


def command_checkpoint_cot(args: argparse.Namespace) -> int:
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
    append_cot_event(root, event)
    update_latest(root, trace_id)
    print(str(cot_events_path(root, trace_id)))
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


def command_render_cot(args: argparse.Namespace) -> int:
    root = data_root(args)
    trace_id = resolve_trace_id(root, args)
    outputs = render_cot_trace(root, trace_id, max_nodes=args.max_nodes)
    print(outputs["latest_cot_md"])
    return 0


def add_checkpoint_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--trace-id", help="Trace id. Defaults to latest trace or manual.")
    parser.add_argument("--kind", required=True, choices=sorted(VALID_KINDS))
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--status", choices=sorted(VALID_STATUSES), default="unknown")
    parser.add_argument("--actor", default="")
    parser.add_argument("--target", default="")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--parent-id", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import generic Agent Thought Map events and render a graph.")
    parser.add_argument("--data-dir", help="Trace data directory. Defaults to AGENT_THOUGHT_MAP_DATA, then .agent-thought-map-data.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    checkpoint = subparsers.add_parser("checkpoint", help="Append an explicit generic checkpoint event.")
    add_checkpoint_args(checkpoint)
    checkpoint.set_defaults(func=command_checkpoint)

    checkpoint_cot = subparsers.add_parser(
        "checkpoint-cot",
        help="Append an explicit rationale checkpoint event for the separate CoT graph.",
    )
    add_checkpoint_args(checkpoint_cot)
    checkpoint_cot.set_defaults(func=command_checkpoint_cot)

    importer = subparsers.add_parser("import-jsonl", help="Import generic JSONL events.")
    importer.add_argument("--trace-id", help="Trace id. Defaults to latest trace or manual.")
    importer.add_argument("--input", required=True, help="Path to a JSONL file containing generic events.")
    importer.set_defaults(func=command_import_jsonl)

    render = subparsers.add_parser("render", help="Render the latest Mermaid graph.")
    render.add_argument("--trace-id", help="Trace id. Defaults to latest trace or manual.")
    render.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    render.set_defaults(func=command_render)

    render_cot = subparsers.add_parser("render-cot", help="Render the latest rationale Mermaid graph.")
    render_cot.add_argument("--trace-id", help="Trace id. Defaults to latest trace or manual.")
    render_cot.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    render_cot.set_defaults(func=command_render_cot)

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
