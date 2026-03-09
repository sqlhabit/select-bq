"""Select BigQuery CLI - wraps bq with SELECT-only validation, allowlist, and audit logging."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select BigQuery CLI - SELECT-only queries with allowlist and audit logging. Wraps the official bq CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  select-bq query "SELECT 1"
  select-bq query --format=pretty "SELECT * FROM project.dataset.table LIMIT 10"
  select-bq query --use_legacy_sql=false "SELECT 1"
  select-bq query -f query.sql
  select-bq query --config .select-bq.yaml "SELECT * FROM my_dataset.my_table"
        """,
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=Path(".select-bq.yaml"),
        help="Path to config file (default: .select-bq.yaml). Contains allowlist and log_path.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # query subcommand - use parse_known_args to pass through bq flags
    query_parser = subparsers.add_parser("query", help="Run a SELECT query (wraps bq query)")
    query_parser.add_argument(
        "query",
        nargs="?",
        help="SQL query string (or use -f/--filename)",
    )
    query_parser.add_argument(
        "-f",
        "--filename",
        type=Path,
        help="Read query from file",
    )
    query_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only validate query, do not execute (useful for testing)",
    )
    query_parser.add_argument(
        "--use_legacy_sql",
        choices=("true", "false"),
        default="false",
        help="Use legacy SQL dialect (default: false = Standard SQL)",
    )

    args, bq_args = parser.parse_known_args()

    if args.command == "query":
        run_query(args, bq_args)
    else:
        parser.print_help()
        sys.exit(1)


def run_query(args: argparse.Namespace, bq_args: list[str]) -> None:
    from .allowlist import check_allowlist, load_allowlist
    from .logger import append_query_log
    from .validator import ValidationError, extract_table_refs, validate_select_only

    # Resolve query text
    if args.filename:
        if not args.filename.exists():
            print(f"Error: File not found: {args.filename}", file=sys.stderr)
            sys.exit(1)
        query = args.filename.read_text().strip()
    elif args.query:
        query = args.query.strip()
    else:
        print("Error: Provide a query string or -f/--filename", file=sys.stderr)
        sys.exit(1)

    if not query:
        print("Error: Empty query", file=sys.stderr)
        sys.exit(1)

    # Load config
    config_path = args.config
    config: dict = {}
    if config_path.exists():
        try:
            import yaml

            config = yaml.safe_load(config_path.read_text()) or {}
        except Exception as e:
            print(f"Warning: Could not load config: {e}", file=sys.stderr)

    log_path = Path(config.get("log_path", "select-bq-queries.yaml"))

    # Resolve allowlist: external file, or inline in config
    allowlist: list[tuple[str | None, str | None, str]] = []
    allowlist_file = config.get("allowlist_path")
    if allowlist_file:
        allowlist = load_allowlist(Path(allowlist_file))
    else:
        # Inline allowlist in config
        allowlist = load_allowlist(config_path if config.get("allowlist") else None)

    # 1. Validate SELECT-only
    try:
        validate_select_only(query)
    except ValidationError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        append_query_log(log_path, query, success=False, error=str(e))
        sys.exit(1)

    # 2. Check allowlist (only if allowlist exists and is non-empty)

    if allowlist:
        try:
            table_refs = extract_table_refs(query)
            check_allowlist(table_refs, allowlist)
        except ValidationError as e:
            print(f"Allowlist error: {e}", file=sys.stderr)
            append_query_log(log_path, query, success=False, error=str(e))
            sys.exit(1)

    if args.dry_run:
        print("Validation passed. Query is SELECT-only and allowlist check passed.")
        append_query_log(log_path, query, success=True)
        sys.exit(0)

    # 3. Run bq query (pass through unknown args like --format=pretty, --project_id=...)
    use_legacy = getattr(args, "use_legacy_sql", "false")
    bq_cmd = ["bq", "query", f"--use_legacy_sql={use_legacy}"] + bq_args + [query]
    try:
        result = subprocess.run(bq_cmd, capture_output=False)
        success = result.returncode == 0
    except FileNotFoundError:
        print(
            "Error: 'bq' CLI not found. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install",
            file=sys.stderr,
        )
        append_query_log(log_path, query, success=False, error="bq CLI not found")
        sys.exit(1)
    except Exception as e:
        append_query_log(log_path, query, success=False, error=str(e))
        raise

    # 4. Log
    append_query_log(log_path, query, success=success)

    sys.exit(0 if success else result.returncode)
