from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ._common import BridgeError, build_tree_and_stats, collect_git, config_output_dir, now_iso, safe_project_name, sha256_file
from ._evidence import collect_docs, copy_artifacts, execute_checks, markdown_code, pack_sources

def write_snapshot(project: Path, config: dict[str, Any], run_checks: bool, include_source: bool) -> dict[str, Any]:
    output_dir = config_output_dir(project, config)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = now_iso()
    project_cfg = config.get("project", {})
    name = str(project_cfg.get("name") or project.name)
    objective = str(project_cfg.get("objective", ""))
    phase = str(project_cfg.get("phase", ""))
    status = str(project_cfg.get("status", ""))
    git = collect_git(project)
    tree, stats = build_tree_and_stats(project, output_dir, config)
    docs = collect_docs(project, config)
    checks = execute_checks(project, config, run_checks)
    artifacts = copy_artifacts(project, output_dir, config)
    source_pack = pack_sources(project, config, include_source)

    evidence = {
        "generated_at": generated_at,
        "project": {
            "name": name,
            "objective": objective,
            "phase": phase,
            "status": status,
            "root": str(project),
        },
        "git": git,
        "stats": stats,
        "documents": docs,
        "checks": [asdict(x) for x in checks],
        "artifacts": [asdict(x) for x in artifacts],
        "source_pack": {k: v for k, v in source_pack.items() if k != "content"},
    }

    json_path = output_dir / "PROJECT_SNAPSHOT.json"
    json_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")

    checks_md = ["# Checks", "", f"Generated: {generated_at}", ""]
    if not checks:
        checks_md.append("No checks configured.")
    for result in checks:
        checks_md += [
            f"## {result.name} — {result.status}",
            "",
            f"Command: `{result.command}`",
            f"Return code: `{result.returncode}`",
            f"Duration: `{result.duration_seconds:.2f}s`",
            "",
            "### stdout",
            markdown_code(result.stdout),
            "",
            "### stderr",
            markdown_code(result.stderr),
            "",
        ]
    (output_dir / "CHECKS.md").write_text("\n".join(checks_md), encoding="utf-8")

    art_md = ["# Runtime artifacts", "", "These files are evidence of actual rendered/runtime output, not merely implementation claims.", ""]
    if not artifacts:
        art_md.append("No artifacts matched the configured patterns.")
    else:
        art_md.append("| Label | Source | Snapshot copy | Kind | Modified | SHA-256 |")
        art_md.append("|---|---|---|---|---|---|")
        for a in artifacts:
            art_md.append(f"| {a.label} | `{a.source}` | `{a.copied_to or '(not copied)'}` | {a.kind} | {a.modified_at} | `{a.sha256[:12]}` |")
    (output_dir / "ARTIFACTS.md").write_text("\n".join(art_md), encoding="utf-8")

    source_index = ["# Source index", "", f"Files: **{stats['file_count']}**", f"Total bytes: **{stats['total_size_bytes']}**", "", "## Directory/file listing", "", "```text", tree, "```", "", "## Extension counts", ""]
    for ext, count in stats["extensions"].items():
        source_index.append(f"- `{ext}`: {count}")
    (output_dir / "SOURCE_INDEX.md").write_text("\n".join(source_index), encoding="utf-8")

    if source_pack.get("enabled"):
        (output_dir / "SOURCE_PACK.md").write_text("# Selected source pack\n\n" + source_pack.get("content", ""), encoding="utf-8")
    else:
        sp = output_dir / "SOURCE_PACK.md"
        if sp.exists():
            sp.unlink()

    doc_sections = []
    for d in docs:
        if d.get("status") == "INCLUDED":
            doc_sections.append(f"## {d['path']}\n\n{d['content']}")
        else:
            doc_sections.append(f"## {d['path']}\n\n_Status: {d.get('status')}_")

    snapshot_md = f"""# Project Snapshot — {name}

Generated: {generated_at}

## Declared project state

- Objective: {objective or '(not declared)'}
- Phase: {phase or '(not declared)'}
- Status: {status or '(not declared)'}

## Git implementation evidence

- Git repository: {git.get('is_git_repo', False)}
- Branch: `{git.get('branch', '')}`
- HEAD: `{git.get('head', '')}`
- Dirty worktree: `{git.get('dirty', False)}`
- Origin: `{git.get('remote_origin', '')}`

### Working tree status

{markdown_code(git.get('status_short', ''))}

### Diff stat

{markdown_code(git.get('diff_stat', ''))}

### Staged diff stat

{markdown_code(git.get('staged_diff_stat', ''))}

### Recent commits

{chr(10).join('- ' + x for x in git.get('recent_commits', [])) or '_(none)_'}

## Verification evidence

See `CHECKS.md`.

## Runtime / visual evidence

See `ARTIFACTS.md` and the copied files under `artifacts/`.

## Source map

See `SOURCE_INDEX.md`.

## Included project documents

{chr(10).join(doc_sections) if doc_sections else 'No project documents configured.'}
"""
    (output_dir / "PROJECT_SNAPSHOT.md").write_text(snapshot_md, encoding="utf-8")

    overall_check = "NO_CHECKS"
    if checks:
        statuses = {c.status for c in checks}
        if "FAIL" in statuses or "TIMEOUT" in statuses:
            overall_check = "FAILED"
        elif statuses == {"PASS"}:
            overall_check = "PASSED"
        elif "NOT_RUN" in statuses:
            overall_check = "NOT_RUN"

    entry = f"""# ChatGPT Entry — {name}

> Read this file first. This folder is an evidence-based handoff generated by Codex Context Bridge.

Generated: **{generated_at}**

## What this project is

**Objective:** {objective or '(not declared)'}

**Current phase:** {phase or '(not declared)'}

**Declared status:** {status or '(not declared)'}

## Current evidence summary

- Git branch: `{git.get('branch', '')}`
- Commit: `{git.get('head', '')[:12]}`
- Uncommitted changes: **{'yes' if git.get('dirty') else 'no'}**
- Automated checks: **{overall_check}**
- Runtime/visual artifacts captured: **{len(artifacts)}**
- Project files indexed: **{stats['file_count']}**
- Optional source pack: **{'included' if source_pack.get('enabled') else 'not included'}**

## Evidence hierarchy for ChatGPT

Do **not** treat a developer note saying “done” as proof by itself. Use this order:

1. **Runtime / visual artifacts** (`ARTIFACTS.md` + `artifacts/`) — what the product actually produced.
2. **Automated checks** (`CHECKS.md`) — what was mechanically verified.
3. **Git evidence** (`PROJECT_SNAPSHOT.md`) — what code/version changed.
4. **Project documents** inside `PROJECT_SNAPSHOT.md` — intent, decisions and human/Codex claims.

If these conflict, state the conflict explicitly and prefer stronger evidence. If evidence is missing, say **unknown / not verified**.

## Read next

- `PROJECT_SNAPSHOT.md` — full handoff, Git state, project docs
- `CHECKS.md` — tests/build/lint results
- `ARTIFACTS.md` — screenshots, PNG, HTML, metrics and other outputs
- `SOURCE_INDEX.md` — repository structure
- `PROJECT_SNAPSHOT.json` — machine-readable snapshot
- `SOURCE_PACK.md` — selected source code, only when explicitly generated

## Recommended prompt

> Read the latest ChatGPT Entry and its referenced snapshot files. Separate **declared**, **implemented**, **verified**, and **observed runtime result**. Tell me what has actually changed since the previous development step, what is still unverified, what the strongest blocker is, and what Codex should do next. Do not infer success merely from code existing.
"""
    (output_dir / "CHATGPT_ENTRY.md").write_text(entry, encoding="utf-8")

    manifest_files = []
    for p in sorted(output_dir.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.json":
            manifest_files.append({
                "path": str(p.relative_to(output_dir)).replace("\\", "/"),
                "size": p.stat().st_size,
                "sha256": sha256_file(p),
            })
    (output_dir / "MANIFEST.json").write_text(json.dumps({"generated_at": generated_at, "files": manifest_files}, indent=2, ensure_ascii=False), encoding="utf-8")

    history_cfg = config.get("history", {})
    if bool(history_cfg.get("enabled", True)):
        history = output_dir / "history"
        history.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        history_path = history / f"{stamp}.json"
        shutil.copy2(json_path, history_path)
        keep = max(1, int(history_cfg.get("keep", 20)))
        old = sorted(history.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in old[keep:]:
            p.unlink(missing_ok=True)

    return {"output_dir": str(output_dir), "generated_at": generated_at, "checks": overall_check, "artifacts": len(artifacts), "files_indexed": stats["file_count"]}


def sync_snapshot(project: Path, config: dict[str, Any]) -> Path:
    sync_cfg = config.get("sync", {})
    target = str(sync_cfg.get("target", "")).strip()
    if not target:
        raise BridgeError("No [sync].target configured. Point it at a local Google Drive/OneDrive/Dropbox synced folder.")
    output_dir = config_output_dir(project, config)
    if not output_dir.exists():
        raise BridgeError("Snapshot output does not exist. Run `ccb snapshot` first.")
    name = safe_project_name(str(config.get("project", {}).get("name") or project.name))
    dest_root = Path(os.path.expandvars(os.path.expanduser(target))).resolve()
    dest = dest_root / name
    temp = dest_root / f".{name}.tmp"
    dest_root.mkdir(parents=True, exist_ok=True)
    if temp.exists():
        shutil.rmtree(temp)
    shutil.copytree(output_dir, temp)
    if dest.exists():
        shutil.rmtree(dest)
    temp.replace(dest)
    return dest
