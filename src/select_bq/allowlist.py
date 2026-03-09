"""Allowlist config for project/dataset/table access control."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .validator import TableRef, ValidationError


def load_allowlist(path: Path | None) -> list[tuple[str | None, str | None, str]]:
    """
    Load allowlist from YAML config. Returns list of (project, dataset, table) tuples.
    None means wildcard for project/dataset. '*' for table means all tables in dataset.

    Config format:
        allowlist:
          - project: my-project
            dataset: my_dataset
            table: my_table
          - project: other
            dataset: ds
            table: "*"   # all tables in ds

    Returns empty list if path is None or file doesn't exist or allowlist key is empty.
    """
    if path is None or not path.exists():
        return []

    try:
        data = yaml.safe_load(path.read_text())
    except Exception as e:
        raise ValidationError(f"Failed to load allowlist config: {e}") from e

    if not data or not isinstance(data, dict):
        return []

    entries = data.get("allowlist")
    if entries is None or (isinstance(entries, list) and len(entries) == 0):
        return []

    result: list[tuple[str | None, str | None, str]] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValidationError(f"Allowlist entry {i} must be a dict with project/dataset/table")
        project = entry.get("project")
        dataset = entry.get("dataset")
        table = entry.get("table")
        if table is None or table == "":
            raise ValidationError(f"Allowlist entry {i} must have a 'table' field")
        result.append(
            (
                str(project).strip() if project else None,
                str(dataset).strip() if dataset else None,
                str(table).strip(),
            )
        )
    return result


def check_allowlist(
    table_refs: list[TableRef],
    allowlist: list[tuple[str | None, str | None, str]],
) -> None:
    """
    Raise ValidationError if any table ref is not in the allowlist.
    If allowlist is empty, this check is skipped (allow all).
    """
    if not allowlist:
        return

    for ref in table_refs:
        matched = any(ref.matches_allowlist_entry(entry) for entry in allowlist)
        if not matched:
            display = ".".join(x or "?" for x in [ref.project, ref.dataset, ref.table])
            raise ValidationError(
                f"Table '{display}' is not in the allowlist. "
                "Add it to the allowlist config to allow access."
            )
