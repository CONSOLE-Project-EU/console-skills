#!/usr/bin/env python3
"""CONSOLE AI Skill CLI.

Usage examples:
  console-skill scan .
  console-skill scan . --pr main...feature-branch
  console-skill config --server https://dashboard.consoleproject.eu/api/v1 --api-key <key>
"""

import argparse
import sys
import json
from pathlib import Path

from console_skill import (
    Config,
    ConfigMissingError,
    DEFAULT_SERVER,
    create_job,
    find_git_root,
    get_clues,
    load_config,
    poll_job,
    write_config,
)


def cmd_scan(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve()
    try:
        config = load_config(project_dir)
    except ConfigMissingError as exc:
        print(exc, file=sys.stderr)
        return 1

    version = args.version
    details = args.details
    if args.pr:
        details = (details or "") + f"\nPR scan: {args.pr}"

    print(f"Creating CONSOLE job for {project_dir.name}...")
    job_id = create_job(
        config,
        project_dir,
        project_version=version,
        details=details,
    )
    print(f"Job created: {job_id}")

    print("Polling for results...")
    status = poll_job(config, job_id, timeout_seconds=args.timeout, interval_seconds=args.interval)
    if isinstance(status, dict) and status.get("status") == "failed":
        print(f"CONSOLE job failed: {status}", file=sys.stderr)
        return 1

    print("Retrieving clues...")
    clues = get_clues(config, job_id)
    print(json.dumps(clues, indent=4))

    return 0


def cmd_config(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve()
    server_url = args.server or DEFAULT_SERVER
    api_key = args.api_key
    if not api_key:
        print("--api-key is required", file=sys.stderr)
        return 1
    write_config(project_dir, server_url, api_key)
    print(f"Configuration saved to {project_dir / '.console-skill.json'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="console-skill",
        description="Analyze a project with the CONSOLE security platform.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan a project directory")
    scan_parser.add_argument("project_dir", help="Project directory to scan")
    scan_parser.add_argument(
        "--pr",
        metavar="BASE...HEAD",
        help="Filter results to files changed in a PR (e.g., main...feature)",
    )
    scan_parser.add_argument("--version", help="Project version label")
    scan_parser.add_argument("--details", help="Scan details / context")
    scan_parser.add_argument("--timeout", type=int, default=600, help="Polling timeout in seconds")
    scan_parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds")
    scan_parser.set_defaults(func=cmd_scan)

    config_parser = subparsers.add_parser("config", help="Configure the skill for a project")
    config_parser.add_argument("project_dir", nargs="?", default=".", help="Project directory")
    config_parser.add_argument("--server", default=DEFAULT_SERVER, help="CONSOLE server URL")
    config_parser.add_argument("--api-key", required=True, help="CONSOLE API key")
    config_parser.set_defaults(func=cmd_config)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
