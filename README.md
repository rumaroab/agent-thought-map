# Agent Thought Map

Agent Thought Map turns observable agent progress into a compact Mermaid flowchart.

The core implementation is agent-agnostic. It reads generic JSONL events and writes:

- `latest.mmd`
- `latest.md`
- `trace.json`

Codex support is a thin adapter around that core. The adapter receives Codex lifecycle-hook events, converts them into the generic event schema, and appends them to the same local JSONL trace.

The project does not expose hidden chain-of-thought, token-by-token reasoning, raw transcripts, full tool output, or secrets.

Rendered graphs may include inferred edge labels such as `led to`, `therefore`, and `verify`. These connect adjacent steps into a readable narrative, but they are a reconstruction from observable events, not a literal transcript of the model's reasoning.

## Requirements

- Python 3
- No external dependencies (stdlib only)

## Quickstart

Clone the repository and run the generic CLI:

```bash
git clone https://github.com/rumaroab/agent-thought-map.git
cd agent-thought-map

python3 scripts/agent_thought_map.py checkpoint --trace-id demo --kind goal --title "User goal" --summary "Short summary"
python3 scripts/agent_thought_map.py render --trace-id demo
```

This writes a Mermaid graph under `.agent-thought-map-data/traces/demo/`.

## Codex Plugin Install

To use this as a Codex plugin, point Codex at this directory. The plugin manifest is in [`.codex-plugin/plugin.json`](.codex-plugin/plugin.json), and lifecycle hooks are configured in [`hooks/hooks.json`](hooks/hooks.json).

## Version 0.1 Shape

This MVP is intentionally small:

- portable event schema and renderer
- one generic CLI
- one Codex hook adapter
- one Claude Code hook adapter
- one OpenCode plugin bridge
- one bundled Codex skill
- lifecycle hook configuration
- local JSONL storage

No MCP server, Apps SDK UI, database, cloud sync, adapter framework, inheritance hierarchy, or additional runtime adapter beyond Codex, Claude Code, and OpenCode is included.

## Generic Event Schema

Generic events are JSON objects, one per line:

```json
{
  "trace_id": "demo",
  "kind": "investigation",
  "title": "Inspect relevant files",
  "summary": "Read the current implementation and docs.",
  "status": "ok",
  "source": "manual",
  "actor": "agent",
  "target": "scripts/",
  "tags": ["source-read"],
  "parent_id": "",
  "native_ref": {}
}
```

Supported `kind` values:

- `goal`
- `plan`
- `investigation`
- `discovery`
- `decision`
- `action`
- `retry`
- `validation`
- `result`

Supported `status` values are `ok`, `failed`, `blocked`, and `unknown`.

## Runtime Data

Traces are stored under:

```text
<data-dir>/traces/<trace_id>/
```

For portable use, set:

```bash
AGENT_THOUGHT_MAP_DATA=/tmp/agent-thought-map
```

If no data directory is configured, the generic CLI writes to `.agent-thought-map-data` in the current directory.

The Codex adapter may fall back to `PLUGIN_DATA` when Codex provides it.

## Generic CLI

Create a checkpoint:

```bash
python3 scripts/agent_thought_map.py checkpoint --trace-id demo --kind goal --title "User goal" --summary "Short summary"
```

Import generic JSONL:

```bash
python3 scripts/agent_thought_map.py import-jsonl --trace-id demo --input events.jsonl
```

Render:

```bash
python3 scripts/agent_thought_map.py render --trace-id demo
```

## Codex Adapter

`hooks/hooks.json` invokes:

```bash
python3 "$PLUGIN_ROOT/scripts/codex_adapter.py" collect
```

The adapter implements only three steps:

1. read native Codex hook JSON from stdin
2. normalize it into the generic event schema
3. append the generic event when the trace is active

The core renderer does not depend on Codex hook names, Codex transcript formats, `PLUGIN_DATA`, Codex session identifiers, or Codex-specific tool names.

## Claude Code Adapter

Set the plugin root and merge [`hooks/claude/settings.json`](hooks/claude/settings.json) into your user or project `.claude/settings.json`:

```bash
export AGENT_THOUGHT_MAP_ROOT=/path/to/agent-thought-map
```

The hooks invoke:

```bash
python3 "$AGENT_THOUGHT_MAP_ROOT/scripts/claude_adapter.py" collect
```

Claude command hooks pass JSON on stdin with `hook_event_name`, `session_id`, `tool_name`, and `tool_input`. The adapter normalizes those events into the same generic JSONL schema.

Optional data directory:

```bash
export AGENT_THOUGHT_MAP_DATA=/tmp/agent-thought-map
```

The Claude adapter may also fall back to `CLAUDE_PLUGIN_DATA` when Claude provides it.

## OpenCode Adapter

OpenCode uses a JavaScript plugin bridge plus a Python adapter.

1. Copy or symlink [`plugin/opencode/thought-map.js`](plugin/opencode/thought-map.js) into `.opencode/plugins/` for the project, or into `~/.config/opencode/plugins/` for global use.
2. The bridge listens to `tool.execute.after` and selected `session.*` events, then pipes compact JSON to:

```bash
python3 /path/to/agent-thought-map/scripts/opencode_adapter.py collect
```

3. Activate a trace with the generic CLI before expecting graph updates:

```bash
python3 scripts/agent_thought_map.py checkpoint --trace-id demo --kind goal --title "User goal" --summary "Short summary"
```

The OpenCode bridge uses `Bun.spawn` to pipe stdin into the Python adapter. It does not parse transcripts or store full tool output.

## Adding Another Runtime Later

Do not add a broad adapter framework. Another runtime should add one small script that follows the same adapter shape:

1. read native event
2. normalize event
3. append generic event

The new adapter should call functions from `scripts/thought_map_core.py` and write the same generic JSONL schema.

Codex, Claude Code, and OpenCode already follow this pattern with standalone adapters in `scripts/`.

## Privacy

The core and adapters store normalized summaries instead of raw native payloads. They redact common secrets and avoid transcript parsing. File paths, commands, or short targets may appear; file contents and large command outputs are not stored.

## Validation

Validate the plugin manifest with:

```bash
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```
