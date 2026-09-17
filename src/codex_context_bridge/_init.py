from __future__ import annotations

from pathlib import Path

from ._common import DEFAULT_CONFIG

def default_config_text(project_name: str) -> str:
    safe = project_name.replace('"', "'")
    return f'''# Codex Context Bridge project configuration

[project]
name = "{safe}"
objective = "Describe the user-facing goal here"
phase = "Current phase"
status = "active"

[bridge]
output_dir = ".ai-context"
max_tree_entries = 1500
ignore = ["*.log", "tmp/**", "temp/**"]

[documents]
include = ["README.md", "AGENTS.md", "STATE.md", "DECISIONS.md", "ROADMAP.md"]
max_chars_per_file = 30000

# Checks are only executed when you run: ccb snapshot --run-checks
[[checks]]
name = "tests"
command = "python -m pytest -q"
timeout = 180

# Add output evidence produced by the application. Latest matching files are copied.
# [[artifacts]]
# name = "latest-route-png"
# glob = "output/**/*.png"
# limit = 3
# copy = true
#
# [[artifacts]]
# name = "metrics"
# glob = "output/**/*metrics*.json"
# limit = 3
# copy = true

[source_pack]
# Source code is NOT packed by default. Add precise globs and use --include-source.
include = ["src/**/*.py"]
max_chars_per_file = 20000
max_total_chars = 180000

[history]
enabled = true
keep = 20

[sync]
# Example Windows Google Drive Desktop path:
# target = "G:/My Drive/AI Context"
target = ""
'''


def initialize_project(project: Path, force: bool = False) -> list[Path]:
    project.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    config = project / DEFAULT_CONFIG
    if force or not config.exists():
        config.write_text(default_config_text(project.name), encoding="utf-8")
        created.append(config)
    state = project / "STATE.md"
    if not state.exists():
        state.write_text("""# Project State

## Current phase

Describe the phase Codex is working on.

## Implemented

- Nothing verified yet.

## Verified

- Nothing verified yet.

## Current blockers

- None recorded.

## Next step

- Define the next concrete step.
""", encoding="utf-8")
        created.append(state)
    decisions = project / "DECISIONS.md"
    if not decisions.exists():
        decisions.write_text("# Decisions\n\nRecord important architectural/product decisions and why they were made.\n", encoding="utf-8")
        created.append(decisions)
    return created
