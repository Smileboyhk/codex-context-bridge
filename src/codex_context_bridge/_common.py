from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

DEFAULT_CONFIG = ".ccb.toml"
DEFAULT_OUTPUT = ".ai-context"

BLOCKED_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "service-account.json",
}
BLOCKED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
DEFAULT_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    DEFAULT_OUTPUT,
}
TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".toml",
    ".yaml", ".yml", ".html", ".css", ".scss", ".sql", ".sh", ".ps1", ".bat",
    ".cmd", ".java", ".kt", ".go", ".rs", ".c", ".cc", ".cpp", ".h", ".hpp",
    ".cs", ".php", ".rb", ".swift", ".dart", ".vue", ".svelte",
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}

SECRET_PATTERNS = [
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_ACCESS_KEY]"),
    (re.compile(r"(?i)(password|passwd|pwd|api[_-]?key|secret|token)\s*[:=]\s*([^\s\"']{6,})"), r"\1=[REDACTED]"),
]


@dataclass
class CheckResult:
    name: str
    command: str
    returncode: int | None
    status: str
    duration_seconds: float
    stdout: str
    stderr: str


@dataclass
class ArtifactRecord:
    label: str
    source: str
    copied_to: str | None
    size_bytes: int
    modified_at: str
    sha256: str
    kind: str


class BridgeError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def safe_project_name(name: str) -> str:
    # Keep Unicode project names while removing Windows-invalid path characters.
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", name.strip())
    value = re.sub(r"\s+", "-", value).strip("-. ")
    return value or "project"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def redact_text(text: str) -> tuple[str, int]:
    total = 0
    for pattern, replacement in SECRET_PATTERNS:
        text, count = pattern.subn(replacement, text)
        total += count
    return text, total


def is_blocked(path: Path) -> bool:
    name = path.name.lower()
    if name in BLOCKED_NAMES or path.suffix.lower() in BLOCKED_SUFFIXES:
        return True
    if name.startswith(".env."):
        return True
    return False


def read_text_limited(path: Path, max_chars: int) -> tuple[str, bool, int]:
    if is_blocked(path):
        raise BridgeError(f"Refusing to read sensitive-looking file: {path}")
    raw = path.read_text(encoding="utf-8", errors="replace")
    redacted, hits = redact_text(raw)
    truncated = len(redacted) > max_chars
    if truncated:
        redacted = redacted[:max_chars] + "\n\n[TRUNCATED]\n"
    return redacted, truncated, hits


def run_git(project: Path, args: list[str], timeout: int = 10) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=project,
            text=True,
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def collect_git(project: Path) -> dict[str, Any]:
    inside = run_git(project, ["rev-parse", "--is-inside-work-tree"]) == "true"
    if not inside:
        return {"is_git_repo": False}
    branch = run_git(project, ["branch", "--show-current"])
    head = run_git(project, ["rev-parse", "HEAD"])
    remote = run_git(project, ["remote", "get-url", "origin"])
    status = run_git(project, ["status", "--short"])
    diff_stat = run_git(project, ["diff", "--stat"])
    staged_diff_stat = run_git(project, ["diff", "--cached", "--stat"])
    recent = run_git(
        project,
        ["log", "-8", "--date=short", "--pretty=format:%h | %ad | %s"],
    )
    return {
        "is_git_repo": True,
        "branch": branch or "(detached/unknown)",
        "head": head,
        "remote_origin": remote,
        "dirty": bool(status),
        "status_short": status,
        "diff_stat": diff_stat,
        "staged_diff_stat": staged_diff_stat,
        "recent_commits": recent.splitlines() if recent else [],
    }


def load_config(project: Path, config_path: str | None = None) -> dict[str, Any]:
    path = Path(config_path).expanduser().resolve() if config_path else project / DEFAULT_CONFIG
    if not path.exists():
        raise BridgeError(f"Config not found: {path}. Run `ccb init` first.")
    if tomllib is None:
        raise BridgeError("Python 3.11+ is required (tomllib missing).")
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    data["_config_path"] = str(path)
    return data


def config_output_dir(project: Path, config: dict[str, Any]) -> Path:
    out = config.get("bridge", {}).get("output_dir", DEFAULT_OUTPUT)
    out_path = Path(out)
    if not out_path.is_absolute():
        out_path = project / out_path
    return out_path.resolve()


def iter_project_files(project: Path, output_dir: Path, extra_ignores: Iterable[str]) -> Iterable[Path]:
    ignore_dirs = set(DEFAULT_IGNORE_DIRS)
    ignore_dirs.add(output_dir.name)
    ignore_globs = list(extra_ignores)
    for root, dirs, files in os.walk(project):
        root_path = Path(root)
        dirs[:] = [
            d for d in dirs
            if d not in ignore_dirs
            and not any(fnmatch.fnmatch(str((root_path / d).relative_to(project)).replace("\\", "/"), g) for g in ignore_globs)
        ]
        for filename in files:
            p = root_path / filename
            rel = str(p.relative_to(project)).replace("\\", "/")
            if any(fnmatch.fnmatch(rel, g) for g in ignore_globs):
                continue
            if is_blocked(p):
                continue
            yield p


def build_tree_and_stats(project: Path, output_dir: Path, config: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    bridge_cfg = config.get("bridge", {})
    max_entries = int(bridge_cfg.get("max_tree_entries", 1500))
    extra_ignores = bridge_cfg.get("ignore", [])
    rows: list[str] = []
    ext_counts: dict[str, int] = {}
    total_size = 0
    count = 0
    for p in iter_project_files(project, output_dir, extra_ignores):
        rel = str(p.relative_to(project)).replace("\\", "/")
        count += 1
        if len(rows) < max_entries:
            rows.append(rel)
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        total_size += size
        suffix = p.suffix.lower() or "[no-extension]"
        ext_counts[suffix] = ext_counts.get(suffix, 0) + 1
    tree_text = "\n".join(rows)
    if count > max_entries:
        tree_text += f"\n... [{count - max_entries} more files omitted]"
    stats = {
        "file_count": count,
        "total_size_bytes": total_size,
        "extensions": dict(sorted(ext_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "tree_entries_included": min(count, max_entries),
    }
    return tree_text, stats

