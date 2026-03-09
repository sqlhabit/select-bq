"""Query logging to YAML file with timestamps."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def append_query_log(
    log_path: Path,
    query: str,
    *,
    success: bool = True,
    error: str | None = None,
) -> None:
    """
    Append a query execution record to the YAML log file.
    Format: list of entries with timestamp, query, success, and optional error.
    """
    now = datetime.now(timezone.utc).isoformat()

    entry: dict[str, Any] = {
        "timestamp": now,
        "query": query,
        "success": success,
    }
    if error:
        entry["error"] = error

    # Ensure parent dir exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing log or initialize
    if log_path.exists():
        try:
            data = yaml.safe_load(log_path.read_text())
        except Exception:
            data = {"queries": []}
    else:
        data = {"queries": []}

    if not isinstance(data, dict):
        data = {"queries": []}
    if "queries" not in data:
        data["queries"] = []

    data["queries"].append(entry)

    # Write back (append-style by reloading - for simplicity; for high throughput use append)
    with log_path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
