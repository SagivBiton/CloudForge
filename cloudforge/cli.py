"""
cloudforge/cli.py

Command-line interface for CloudForge.

Subcommands:
  modify   Run the modifier agent against a local issue file and YAML config.
           Fast inner dev loop — no GitHub needed.
  run      Start the GitHub Issues poller (same as python -m cloudforge.main).

Usage:
  python -m cloudforge.cli modify --issue examples/issue.md --yaml yamls/s3_discovery.yaml
  python -m cloudforge.cli run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def cmd_modify(args: argparse.Namespace) -> None:
    issue_path = Path(args.issue)
    yaml_path = Path(args.yaml)

    if not issue_path.exists():
        print(f"Error: issue file not found: {issue_path}", file=sys.stderr)
        sys.exit(1)
    if not yaml_path.exists():
        print(f"Error: YAML file not found: {yaml_path}", file=sys.stderr)
        sys.exit(1)

    issue_text = issue_path.read_text()
    # First line is the title, rest is the body
    lines = issue_text.strip().splitlines()
    issue_title = lines[0].strip()
    issue_body = "\n".join(lines[1:]).strip()

    current_yaml = yaml_path.read_text()

    print(f"Running modifier for: {issue_title!r}", file=sys.stderr)

    from cloudforge.agent.modifier import run_modifier
    config = run_modifier(
        issue_title=issue_title,
        issue_body=issue_body,
        current_yaml=current_yaml,
    )

    output = yaml.safe_dump(
        config.model_dump(exclude_none=True),
        default_flow_style=False,
        sort_keys=False,
    )
    print(output)


def cmd_run(_args: argparse.Namespace) -> None:
    from cloudforge.github_app.poller import run_forever
    run_forever()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cloudforge",
        description="CloudForge — automated YAML discovery config updates",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # modify
    modify_p = subparsers.add_parser(
        "modify",
        help="Run the modifier agent against a local issue file (no GitHub needed)",
    )
    modify_p.add_argument(
        "--issue",
        required=True,
        help="Path to a text file: first line = title, rest = body",
    )
    modify_p.add_argument(
        "--yaml",
        required=True,
        default="yamls/s3_discovery.yaml",
        help="Path to the current discovery YAML (default: yamls/s3_discovery.yaml)",
    )

    # run
    subparsers.add_parser(
        "run",
        help="Start the GitHub Issues poller",
    )

    args = parser.parse_args()
    if args.command == "modify":
        cmd_modify(args)
    elif args.command == "run":
        cmd_run(args)


if __name__ == "__main__":
    main()
