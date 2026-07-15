# Contributing

Thanks for your interest in Agent Thought Map.

## Design Philosophy

Read [AGENTS.md](AGENTS.md) before making changes. The project prioritizes simplicity: implement the smallest solution that satisfies the current requirement, build the happy path first, and avoid speculative abstractions.

## Getting Started

1. Clone the repository.
2. Run the generic CLI (Python 3, no external dependencies):

```bash
python3 scripts/agent_thought_map.py checkpoint --trace-id demo --kind goal --title "User goal" --summary "Short summary"
python3 scripts/agent_thought_map.py render --trace-id demo
```

3. If you have the Codex plugin-creator skill installed, validate the plugin manifest:

```bash
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

## Pull Requests

Keep changes focused and small. Match the existing style and avoid adding dependencies unless there is a clear need.
