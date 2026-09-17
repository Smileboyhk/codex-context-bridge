from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._common import (
    ArtifactRecord, BridgeError, CheckResult, IMAGE_SUFFIXES, TEXT_SUFFIXES,
    is_blocked, read_text_limited, redact_text, safe_project_name, sha256_file,
)

def expand_glob(project: Path, pattern: str) -> list[Path]:
    matches = []
    for p in project.glob(pattern):
        try:
            rp = p.resolve()
            rp.relative_to(project.resolve())
        except (ValueError, OSError):
            continue
        if p.is_file() and not is_blocked(p):
            matches.append(p)
    return matches


def copy_artifacts(project: Path, output_dir: Path, config: dict[str, Any]) -> list[ArtifactRecord]:
    records: list[ArtifactRecord] = []
    artifact_dir = output_dir / "artifacts"
    # A snapshot must only contain current evidence; stale artifacts are dangerous.
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for spec in config.get("artifacts", []):
        label = str(spec.get("name") or spec.get("glob") or "artifact")
        pattern = str(spec.get("glob", ""))
        if not pattern:
            continue
        limit = max(1, int(spec.get("limit", 3)))
        should_copy = bool(spec.get("copy", True))
        matches = expand_glob(project, pattern)
        matches.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        filtered: list[Path] = []
        for candidate in matches:
            try:
                candidate.resolve().relative_to(output_dir.resolve())
                continue
            except ValueError:
                filtered.append(candidate)
        for p in filtered[:limit]:
            rel = str(p.relative_to(project)).replace("\\", "/")
            copied_to: str | None = None
            if should_copy:
                subdir = artifact_dir / safe_project_name(label)
                subdir.mkdir(parents=True, exist_ok=True)
                dest = subdir / p.name
                if dest.exists() and dest.resolve() != p.resolve():
                    stem, suffix = dest.stem, dest.suffix
                    dest = subdir / f"{stem}-{sha256_file(p)[:8]}{suffix}"
                shutil.copy2(p, dest)
                copied_to = str(dest.relative_to(output_dir)).replace("\\", "/")
            stat = p.stat()
            kind = "image" if p.suffix.lower() in IMAGE_SUFFIXES else ("text" if p.suffix.lower() in TEXT_SUFFIXES else "binary")
            records.append(
                ArtifactRecord(
                    label=label,
                    source=rel,
                    copied_to=copied_to,
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
                    sha256=sha256_file(p),
                    kind=kind,
                )
            )
    return records


def execute_checks(project: Path, config: dict[str, Any], enabled: bool) -> list[CheckResult]:
    results: list[CheckResult] = []
    for spec in config.get("checks", []):
        name = str(spec.get("name", "check"))
        command = str(spec.get("command", "")).strip()
        timeout = int(spec.get("timeout", 120))
        if not command:
            continue
        if not enabled:
            results.append(CheckResult(name, command, None, "NOT_RUN", 0.0, "", "Run snapshot with --run-checks."))
            continue
        start = datetime.now(timezone.utc)
        try:
            proc = subprocess.run(
                command,
                cwd=project,
                shell=True,
                text=True,
                capture_output=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            end = datetime.now(timezone.utc)
            status = "PASS" if proc.returncode == 0 else "FAIL"
            stdout, _ = redact_text(proc.stdout[-12000:])
            stderr, _ = redact_text(proc.stderr[-12000:])
            results.append(CheckResult(name, command, proc.returncode, status, (end - start).total_seconds(), stdout, stderr))
        except subprocess.TimeoutExpired as exc:
            end = datetime.now(timezone.utc)
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            results.append(CheckResult(name, command, None, "TIMEOUT", (end - start).total_seconds(), stdout[-12000:], stderr[-12000:]))
    return results


def collect_docs(project: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    docs_cfg = config.get("documents", {})
    files = list(docs_cfg.get("include", []))
    max_chars = int(docs_cfg.get("max_chars_per_file", 30000))
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in files:
        rel = str(item).replace("\\", "/")
        if rel in seen:
            continue
        seen.add(rel)
        p = (project / rel).resolve()
        try:
            p.relative_to(project.resolve())
        except ValueError:
            result.append({"path": rel, "status": "REFUSED_OUTSIDE_PROJECT"})
            continue
        if not p.exists() or not p.is_file():
            result.append({"path": rel, "status": "MISSING"})
            continue
        try:
            content, truncated, redactions = read_text_limited(p, max_chars)
        except (BridgeError, OSError) as exc:
            result.append({"path": rel, "status": "REFUSED", "error": str(exc)})
            continue
        result.append({
            "path": rel,
            "status": "INCLUDED",
            "sha256": sha256_file(p),
            "truncated": truncated,
            "redactions": redactions,
            "content": content,
        })
    return result


def pack_sources(project: Path, config: dict[str, Any], enabled: bool) -> dict[str, Any]:
    cfg = config.get("source_pack", {})
    patterns = cfg.get("include", [])
    max_file_chars = int(cfg.get("max_chars_per_file", 20000))
    max_total_chars = int(cfg.get("max_total_chars", 180000))
    if not enabled or not patterns:
        return {"enabled": False, "reason": "not requested or no include patterns", "files": [], "content": ""}
    files: list[Path] = []
    for pattern in patterns:
        files.extend(expand_glob(project, str(pattern)))
    dedup: dict[str, Path] = {}
    for p in files:
        rel = str(p.relative_to(project)).replace("\\", "/")
        dedup[rel] = p
    output: list[str] = []
    included: list[dict[str, Any]] = []
    total = 0
    for rel in sorted(dedup):
        p = dedup[rel]
        if p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content, truncated, redactions = read_text_limited(p, max_file_chars)
        except (BridgeError, OSError):
            continue
        block = f"## File: {rel}\n\n```text\n{content}\n```\n"
        if total + len(block) > max_total_chars:
            break
        output.append(block)
        total += len(block)
        included.append({"path": rel, "sha256": sha256_file(p), "truncated": truncated, "redactions": redactions})
    return {"enabled": True, "files": included, "content": "\n".join(output), "total_chars": total}


def markdown_code(value: str) -> str:
    if not value:
        return "_(none)_"
    return "```text\n" + value.rstrip() + "\n```"

