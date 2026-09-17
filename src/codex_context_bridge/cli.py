from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import BridgeError, initialize_project, load_config, sync_snapshot, write_snapshot


def project_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ccb", description="Codex-to-ChatGPT evidence-based project handoff")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Add CCB config and state templates to a project")
    p_init.add_argument("--project", default=".", help="Project directory (default: current directory)")
    p_init.add_argument("--force", action="store_true", help="Overwrite .ccb.toml if it already exists")

    p_snapshot = sub.add_parser("snapshot", help="Generate a ChatGPT-readable project snapshot")
    p_snapshot.add_argument("--project", default=".", help="Project directory")
    p_snapshot.add_argument("--config", default=None, help="Alternate config path")
    p_snapshot.add_argument("--run-checks", action="store_true", help="Execute configured verification commands")
    p_snapshot.add_argument("--include-source", action="store_true", help="Include configured source pack")
    p_snapshot.add_argument("--sync", action="store_true", help="Copy the generated snapshot to configured sync target")

    p_sync = sub.add_parser("sync", help="Copy the latest snapshot to a local cloud-sync folder")
    p_sync.add_argument("--project", default=".", help="Project directory")
    p_sync.add_argument("--config", default=None, help="Alternate config path")

    p_doctor = sub.add_parser("doctor", help="Check whether the project is configured")
    p_doctor.add_argument("--project", default=".", help="Project directory")
    p_doctor.add_argument("--config", default=None, help="Alternate config path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            project = project_path(args.project)
            created = initialize_project(project, force=args.force)
            if created:
                for p in created:
                    print(f"created: {p}")
            else:
                print("already configured")
            return 0

        project = project_path(args.project)
        config = load_config(project, args.config)

        if args.command == "snapshot":
            result = write_snapshot(project, config, run_checks=args.run_checks, include_source=args.include_source)
            if args.sync:
                result["synced_to"] = str(sync_snapshot(project, config))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        if args.command == "sync":
            print(sync_snapshot(project, config))
            return 0

        if args.command == "doctor":
            print(f"OK: configuration loaded from {config.get('_config_path')}")
            print(f"Project: {config.get('project', {}).get('name', project.name)}")
            return 0

    except BridgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    return 1
