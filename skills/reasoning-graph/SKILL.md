---
name: reasoning-graph
description: Create or render an Agent Thought Map Mermaid graph from generic observable events, explicit checkpoints, tool summaries, retries, validation, and final result. Use when the user asks for Agent Thought Map, thought map, reasoning graph, observable process graph, or a compact Mermaid summary of agent work.
---

# Reasoning Graph

Use this skill when the user wants an Agent Thought Map for the current task.

The core workflow is agent-agnostic. It consumes generic JSONL events and renders Mermaid, Markdown, and normalized JSON. Codex hooks are only one adapter into that generic event format.

Do not expose hidden chain-of-thought, token-by-token reasoning, raw transcripts, full terminal output, secrets, credentials, or private file contents. Record only observable, high-level summaries.

## Script

The plugin root is two directories above this `SKILL.md`. Use:

```bash
python3 "$PLUGIN_ROOT/scripts/agent_thought_map.py"
```

If `PLUGIN_ROOT` is not available in a shell command, resolve the absolute plugin root from this skill file path and call `scripts/agent_thought_map.py` directly.

## Workflow

1. At the start of the task, checkpoint the user goal:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/agent_thought_map.py" checkpoint --kind goal --title "User goal" --summary "Short observable summary"
   ```

2. After choosing an approach, checkpoint the selected plan:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/agent_thought_map.py" checkpoint --kind plan --title "Selected plan" --summary "Short plan summary"
   ```

3. During the task, add checkpoints only for meaningful progress:

   - `investigation`: important files, systems, docs, or code paths inspected.
   - `discovery`: facts that changed the understanding of the task.
   - `decision`: selected direction or rejected alternative.
   - `action`: implementation or other concrete work.
   - `retry`: meaningful failed attempt followed by a changed approach.
   - `validation`: tests, checks, builds, or manual verification.
   - `result`: final outcome.

   At each meaningful branch point, add a `discovery`, `decision`, or `retry` checkpoint. The summary should state the *why*: what was learned, why this direction was chosen, or what alternative was rejected. These are observable rationale summaries, not private reasoning tokens.

   Example checkpoints:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/agent_thought_map.py" checkpoint --kind discovery --title "Auth entry point" --summary "Auth is handled in middleware.ts, not in the route handlers."
   python3 "$PLUGIN_ROOT/scripts/agent_thought_map.py" checkpoint --kind decision --title "Patch middleware" --summary "Chose middleware over routes because it is the shared entry point; rejected per-route patches."
   python3 "$PLUGIN_ROOT/scripts/agent_thought_map.py" checkpoint --kind retry --title "Fix lint failure" --summary "First patch failed lint on unused import; removed the import and retried."
   ```

4. At the end of the task, checkpoint the result and render:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/agent_thought_map.py" checkpoint --kind result --title "Task completed" --summary "Final observable result"
   python3 "$PLUGIN_ROOT/scripts/agent_thought_map.py" render
   ```

5. Tell the user where `latest.md`, `latest.mmd`, and `trace.json` were written.

## Checkpoint Quality

- Use short titles.
- Use summaries that explain outcomes and rationale, not private reasoning tokens.
- At each branch point, log a `discovery`, `decision`, or `retry` checkpoint that states the why.
- Prefer one checkpoint for a meaningful phase over one per tool call.
- Let adapters capture low-level observable tool events.
- Keep the final graph around 8-15 meaningful nodes.

## Privacy

- Never paste secrets into checkpoint arguments.
- Replace sensitive values with `[REDACTED]`.
- Summarize large outputs instead of copying them.
- Do not read or parse transcript files for this skill.

## Generic JSONL

The portable core accepts JSONL events with these fields:

- `trace_id`
- `kind`
- `title`
- `summary`
- `status`
- `source`
- `actor`
- `target`
- `tags`
- `parent_id`
- `native_ref`

Supported `kind` values are `goal`, `plan`, `investigation`, `discovery`, `decision`, `action`, `retry`, `validation`, and `result`.
