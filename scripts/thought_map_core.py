#!/usr/bin/env python3
"""Portable event storage and Mermaid rendering for Agent Thought Map."""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
import uuid
from pathlib import Path
from typing import Any


PLUGIN_NAME = "agent-thought-map"
DEFAULT_MAX_NODES = 15
VALID_KINDS = {
    "goal",
    "plan",
    "investigation",
    "discovery",
    "decision",
    "action",
    "retry",
    "validation",
    "result",
}
VALID_STATUSES = {"ok", "failed", "blocked", "unknown"}

EDGE_TRANSITION_LABELS: dict[tuple[str, str], str] = {
    ("goal", "plan"): "plan",
    ("plan", "investigation"): "start",
    ("investigation", "discovery"): "found",
    ("investigation", "action"): "so change",
    ("discovery", "decision"): "led to",
    ("decision", "action"): "therefore",
    ("action", "validation"): "verify",
    ("action", "result"): "done",
    ("validation", "result"): "done",
}

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.I | re.S),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(
        r"\b(api[_-]?key|token|secret|password|passwd|authorization|cookie|credential)"
        r"\b\s*[:=]\s*[\"']?[^\"'\s,;]+",
        re.I,
    ),
]
SENSITIVE_KEY_RE = re.compile(r"(key|secret|token|password|passwd|cookie|auth|credential)", re.I)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_trace_id(trace_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", trace_id.strip())[:120].strip("-")
    return safe or "manual"


def trace_dir(data_dir: Path, trace_id: str) -> Path:
    return data_dir / "traces" / safe_trace_id(trace_id)


def events_path(data_dir: Path, trace_id: str) -> Path:
    return trace_dir(data_dir, trace_id) / "events.jsonl"


def cot_events_path(data_dir: Path, trace_id: str) -> Path:
    return trace_dir(data_dir, trace_id) / "cot-events.jsonl"


def active_path(data_dir: Path, trace_id: str) -> Path:
    return trace_dir(data_dir, trace_id) / "active.json"


def latest_path(data_dir: Path) -> Path:
    return data_dir / "latest.json"


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return events
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(normalize_event(value, default_trace_id=value.get("trace_id")))
    return events


def append_event(data_dir: Path, event: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_event(event, default_trace_id=event.get("trace_id"))
    path = events_path(data_dir, normalized["trace_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n")
    return normalized


def append_cot_event(data_dir: Path, event: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_event(event, default_trace_id=event.get("trace_id"))
    path = cot_events_path(data_dir, normalized["trace_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n")
    return normalized


def import_events(data_dir: Path, trace_id: str, events: list[dict[str, Any]]) -> int:
    count = 0
    for event in events:
        append_event(data_dir, normalize_event(event, default_trace_id=trace_id))
        count += 1
    if count:
        activate_trace(data_dir, trace_id)
        update_latest(data_dir, trace_id)
    return count


def activate_trace(data_dir: Path, trace_id: str) -> None:
    write_json(active_path(data_dir, trace_id), {"active": True, "activated_at": utc_now()})


def is_trace_active(data_dir: Path, trace_id: str) -> bool:
    return active_path(data_dir, trace_id).is_file()


def latest_trace_id(data_dir: Path) -> str | None:
    payload = read_json(latest_path(data_dir))
    if payload and isinstance(payload.get("trace_id"), str) and payload["trace_id"].strip():
        return payload["trace_id"].strip()
    return None


def update_latest(data_dir: Path, trace_id: str, outputs: dict[str, str] | None = None) -> None:
    current = read_json(latest_path(data_dir)) or {}
    same_trace = current.get("trace_id") == trace_id
    current_outputs = current.get("outputs") if same_trace else {}
    if not isinstance(current_outputs, dict):
        current_outputs = {}
    payload = {
        **current,
        "plugin": PLUGIN_NAME,
        "trace_id": trace_id,
        "trace_dir": str(trace_dir(data_dir, trace_id)),
        "updated_at": utc_now(),
    }
    if outputs:
        payload["outputs"] = {**current_outputs, **outputs}
    elif not same_trace:
        payload.pop("outputs", None)
    write_json(latest_path(data_dir), payload)


def redact_text(value: str, limit: int = 500) -> str:
    text = value.replace("\x00", "")
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "..."
    return text


def redact_value(value: Any, limit: int = 500) -> Any:
    if isinstance(value, str):
        return redact_text(value, limit=limit)
    if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, list):
        return [redact_value(item, limit=limit) for item in value[:20]]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in list(value.items())[:40]:
            if SENSITIVE_KEY_RE.search(str(key)):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_value(item, limit=limit)
        return redacted
    return redact_text(str(value), limit=limit)


def event_id_for(payload: dict[str, Any]) -> str:
    basis = json.dumps(payload, sort_keys=True, default=str) + utc_now() + str(uuid.uuid4())
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def normalize_event(event: dict[str, Any], default_trace_id: Any = None) -> dict[str, Any]:
    trace_id = str(event.get("trace_id") or default_trace_id or "manual")
    kind = str(event.get("kind") or "discovery").lower()
    if kind not in VALID_KINDS:
        kind = "discovery"
    status = str(event.get("status") or "unknown").lower()
    if status not in VALID_STATUSES:
        status = "unknown"

    tags = event.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    if not isinstance(tags, list):
        tags = []

    normalized = {
        "event_id": redact_text(str(event.get("event_id") or event_id_for(event)), limit=160),
        "trace_id": redact_text(trace_id, limit=160),
        "timestamp": redact_text(str(event.get("timestamp") or utc_now()), limit=80),
        "kind": kind,
        "title": redact_text(str(event.get("title") or kind.title()), limit=120),
        "summary": redact_text(str(event.get("summary") or event.get("title") or kind.title()), limit=500),
        "status": status,
        "source": redact_text(str(event.get("source") or "generic"), limit=80),
        "actor": redact_text(str(event.get("actor") or ""), limit=100),
        "target": redact_text(str(event.get("target") or ""), limit=220),
        "tags": [redact_text(str(tag), limit=60) for tag in tags[:12]],
        "parent_id": redact_text(str(event.get("parent_id") or ""), limit=160),
        "native_ref": redact_value(event.get("native_ref") or {}, limit=200),
    }
    return {key: value for key, value in normalized.items() if value not in ("", [], {})}


def make_event(
    *,
    trace_id: str,
    kind: str,
    title: str,
    summary: str = "",
    status: str = "unknown",
    source: str = "manual",
    actor: str = "",
    target: str = "",
    tags: list[str] | None = None,
    parent_id: str = "",
    native_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return normalize_event(
        {
            "trace_id": trace_id,
            "kind": kind,
            "title": title,
            "summary": summary or title,
            "status": status,
            "source": source,
            "actor": actor,
            "target": target,
            "tags": tags or [],
            "parent_id": parent_id,
            "native_ref": native_ref or {},
        },
        default_trace_id=trace_id,
    )


def render_trace(data_dir: Path, trace_id: str, max_nodes: int = DEFAULT_MAX_NODES) -> dict[str, str]:
    return render_event_trace(
        data_dir=data_dir,
        trace_id=trace_id,
        source_path=events_path(data_dir, trace_id),
        max_nodes=max_nodes,
        markdown_title="Agent Thought Map",
        mmd_name="latest.mmd",
        md_name="latest.md",
        trace_name="trace.json",
        output_keys=("latest_mmd", "latest_md", "trace_json"),
    )


def render_cot_trace(data_dir: Path, trace_id: str, max_nodes: int = DEFAULT_MAX_NODES) -> dict[str, str]:
    return render_event_trace(
        data_dir=data_dir,
        trace_id=trace_id,
        source_path=cot_events_path(data_dir, trace_id),
        max_nodes=max_nodes,
        markdown_title="Agent Thought Map CoT",
        mmd_name="latest-cot.mmd",
        md_name="latest-cot.md",
        trace_name="trace-cot.json",
        output_keys=("latest_cot_mmd", "latest_cot_md", "trace_cot_json"),
    )


def render_event_trace(
    *,
    data_dir: Path,
    trace_id: str,
    source_path: Path,
    max_nodes: int,
    markdown_title: str,
    mmd_name: str,
    md_name: str,
    trace_name: str,
    output_keys: tuple[str, str, str],
) -> dict[str, str]:
    events = read_jsonl(source_path)
    nodes, edges = reduce_events(events, max_nodes=max_nodes)
    out_dir = trace_dir(data_dir, trace_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    mermaid = build_mermaid(nodes, edges)
    mmd_path = out_dir / mmd_name
    md_path = out_dir / md_name
    trace_path = out_dir / trace_name
    mmd_path.write_text(mermaid + "\n", encoding="utf-8")
    md_path.write_text(build_markdown(trace_id, nodes, edges, mermaid, title=markdown_title), encoding="utf-8")
    write_json(
        trace_path,
        {
            "trace_id": trace_id,
            "event_count": len(events),
            "nodes": nodes,
            "edges": edges,
        },
    )

    outputs = {
        output_keys[0]: str(mmd_path),
        output_keys[1]: str(md_path),
        output_keys[2]: str(trace_path),
    }
    update_latest(data_dir, trace_id, outputs=outputs)
    return outputs


def reduce_events(events: list[dict[str, Any]], max_nodes: int = DEFAULT_MAX_NODES) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    nodes: list[dict[str, Any]] = []
    for event in events:
        node = node_from_event(event)
        if nodes and can_merge(nodes[-1], node):
            nodes[-1] = merge_nodes(nodes[-1], node)
        else:
            nodes.append(node)

    limited = limit_nodes(nodes, max_nodes=max_nodes)
    for index, node in enumerate(limited, start=1):
        node["id"] = f"N{index}"

    edges: list[dict[str, str]] = []
    for left, right in zip(limited, limited[1:]):
        edge: dict[str, str] = {"from": left["id"], "to": right["id"]}
        if left.get("kind") == "validation":
            if left.get("status") == "ok":
                edge["label"] = "passed"
            elif left.get("status") == "failed":
                edge["label"] = "failed"
        elif right.get("kind") == "retry":
            edge["label"] = "retry"
        if "label" not in edge:
            label = EDGE_TRANSITION_LABELS.get(
                (str(left.get("kind") or ""), str(right.get("kind") or ""))
            )
            if label:
                edge["label"] = label
        edges.append(edge)
    return limited, edges


def node_from_event(event: dict[str, Any]) -> dict[str, Any]:
    kind = str(event.get("kind") or "discovery")
    return {
        "id": "",
        "kind": kind,
        "title": redact_text(str(event.get("title") or kind.title()), limit=100),
        "summary": redact_text(str(event.get("summary") or event.get("title") or kind.title()), limit=260),
        "status": str(event.get("status") or "unknown"),
        "source": str(event.get("source") or "generic"),
        "actor": str(event.get("actor") or ""),
        "target": str(event.get("target") or ""),
        "tags": list(event.get("tags") or []),
        "event_ids": [str(event.get("event_id") or "")],
        "count": 1,
    }


def can_merge(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("source") == "manual" or right.get("source") == "manual":
        return False
    if left.get("kind") != right.get("kind"):
        return False
    return left.get("actor") == right.get("actor") and left.get("target") == right.get("target")


def merge_nodes(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    count = int(left.get("count", 1)) + int(right.get("count", 1))
    status = "failed" if "failed" in {left.get("status"), right.get("status")} else right.get("status", "unknown")
    summary = str(left.get("summary") or "")
    right_summary = str(right.get("summary") or "")
    if right_summary and right_summary not in summary:
        summary = redact_text(f"{summary}; {right_summary}", limit=260)
    return {
        **left,
        "title": grouped_title(str(left.get("kind") or "discovery"), count),
        "summary": summary,
        "status": status,
        "event_ids": list(left.get("event_ids", [])) + list(right.get("event_ids", [])),
        "count": count,
    }


def grouped_title(kind: str, count: int) -> str:
    titles = {
        "investigation": "Investigate project state",
        "action": "Apply implementation actions",
        "validation": "Run validation checks",
        "retry": "Handle failed attempts",
        "discovery": "Collect discoveries",
        "decision": "Record decisions",
    }
    return f"{titles.get(kind, kind.title())} ({count} events)"


def limit_nodes(nodes: list[dict[str, Any]], max_nodes: int) -> list[dict[str, Any]]:
    limited = list(nodes)
    while len(limited) > max_nodes:
        merged = False
        for index in range(len(limited) - 1):
            if can_merge(limited[index], limited[index + 1]):
                limited[index] = merge_nodes(limited[index], limited[index + 1])
                limited.pop(index + 1)
                merged = True
                break
        if merged:
            continue
        if len(limited) > 2:
            limited[1] = merge_nodes_as_summary(limited[1], limited[2])
            limited.pop(2)
        else:
            break
    return limited


def merge_nodes_as_summary(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {
        **left,
        "title": redact_text(f"{left.get('title')} and related work", limit=100),
        "summary": redact_text(f"{left.get('summary')}; {right.get('summary')}", limit=260),
        "event_ids": list(left.get("event_ids", [])) + list(right.get("event_ids", [])),
        "count": int(left.get("count", 1)) + int(right.get("count", 1)),
    }


def mermaid_label(text: str, limit: int = 80) -> str:
    label = redact_text(text, limit=limit)
    label = label.replace("[", "(").replace("]", ")").replace("{", "(").replace("}", ")")
    label = html.escape(label, quote=True)
    label = label.replace("|", "&#124;")
    return label


def node_shape(node: dict[str, Any]) -> str:
    label = mermaid_label(str(node.get("title") or "Step"))
    if node.get("kind") in {"decision", "validation"}:
        return f'{node["id"]}{{"{label}"}}'
    return f'{node["id"]}["{label}"]'


def build_mermaid(nodes: list[dict[str, Any]], edges: list[dict[str, str]]) -> str:
    lines = ["flowchart TD"]
    if not nodes:
        lines.append('    N1["No trace events recorded"]')
        return "\n".join(lines)
    for node in nodes:
        lines.append(f"    {node_shape(node)}")
    for edge in edges:
        label = edge.get("label")
        if label:
            lines.append(f'    {edge["from"]} -- "{mermaid_label(label, limit=30)}" --> {edge["to"]}')
        else:
            lines.append(f'    {edge["from"]} --> {edge["to"]}')
    return "\n".join(lines)


def build_markdown(
    trace_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, str]],
    mermaid: str,
    title: str = "Agent Thought Map",
) -> str:
    rows = [
        f"# {title}",
        "",
        f"Trace: `{redact_text(trace_id, limit=120)}`",
        "",
        "```mermaid",
        mermaid,
        "```",
        "",
        "## Summary",
        "",
        "| Node | Kind | Status | Summary |",
        "| --- | --- | --- | --- |",
    ]
    for node in nodes:
        rows.append(
            f"| `{node['id']}` | {mermaid_label(str(node.get('kind') or 'discovery'), 40)} | "
            f"{mermaid_label(str(node.get('status') or 'unknown'), 40)} | "
            f"{mermaid_label(str(node.get('summary') or ''), 180)} |"
        )
    rows.extend(["", f"Edges: {len(edges)}", ""])
    return "\n".join(rows)
