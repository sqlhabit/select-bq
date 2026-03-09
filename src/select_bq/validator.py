"""Strict SQL validator - ensures queries are 100% SELECT-only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import sqlglot
from sqlglot import exp

if TYPE_CHECKING:
    from sqlglot.expressions import Expression

# Statement types that are NEVER allowed (data modification, DDL, scripting, etc.)
# We use allowlist: ONLY Select is permitted.
FORBIDDEN_STATEMENT_TYPES = frozenset({
    "Insert", "Update", "Delete", "Merge",
    "Create", "Drop", "Alter", "Truncate", "Rename",
    "Declare", "Set", "Command",  # BigQuery scripting, EXECUTE IMMEDIATE, CALL
    "Grant", "Revoke",
    "Cache", "Uncache", "Refresh",
    "Describe", "Show",  # Could leak schema info but user said SELECT only - exclude to be strict
})

# Keywords to reject before/on parse failure - catches malformed DML (e.g. "DELETE * FROM")
DANGEROUS_SQL_PREFIXES = frozenset({
    "delete", "insert", "update", "merge", "truncate",
    "create", "drop", "alter", "rename",
    "declare", "execute", "call", "grant", "revoke",
})


@dataclass
class TableRef:
    """A BigQuery table reference: project.dataset.table."""

    project: str | None
    dataset: str | None
    table: str

    def to_triple(self) -> tuple[str | None, str | None, str]:
        return (self.project, self.dataset, self.table)

    def matches_allowlist_entry(self, entry: tuple[str | None, str | None, str]) -> bool:
        """Check if this table matches an allowlist entry. None in entry means wildcard."""
        ep, ed, et = entry
        if ep is not None and self.project != ep:
            return False
        if ed is not None and self.dataset != ed:
            return False
        if et != "*" and self.table != et:
            return False
        return True


class ValidationError(Exception):
    """Raised when SQL validation fails."""

    pass


def _first_keyword(sql: str) -> str | None:
    """Extract first keyword from SQL (skips whitespace, comments)."""
    s = sql.strip().lstrip()
    if not s:
        return None
    # Skip single-line and multi-line comments
    while s.startswith("--") or s.startswith("/*"):
        if s.startswith("--"):
            idx = s.find("\n")
            s = s[idx + 1 :].lstrip() if idx >= 0 else ""
        else:
            idx = s.find("*/")
            s = s[idx + 2 :].lstrip() if idx >= 0 else ""
        if not s:
            return None
    # First token (letters, numbers, underscore)
    end = 0
    while end < len(s) and (s[end].isalnum() or s[end] == "_"):
        end += 1
    return s[:end].lower() if end > 0 else None


def validate_select_only(sql: str) -> None:
    """
    Validate that the SQL is 100% SELECT-only. Uses AST parsing - no hackery, evals,
    or hidden CTEs can bypass this.

    Raises:
        ValidationError: If the query contains any non-SELECT statements or dangerous constructs.
    """
    try:
        statements = sqlglot.parse(sql, dialect="bigquery")
    except Exception as e:
        # Parse failed - check if it's malformed DML/DDL (e.g. "DELETE * FROM")
        first = _first_keyword(sql)
        if first and first in DANGEROUS_SQL_PREFIXES:
            raise ValidationError(
                f"Query appears to be a {first.upper()} statement. Only SELECT queries are permitted."
            ) from e
        raise ValidationError(f"Failed to parse SQL: {e}") from e

    if not statements:
        raise ValidationError("Empty or unparseable SQL")

    for stmt in statements:
        if stmt is None:
            raise ValidationError("Empty or malformed statement in SQL (e.g. leading/trailing semicolon).")
        stmt_type = type(stmt).__name__
        if stmt_type != "Select":
            if stmt_type in FORBIDDEN_STATEMENT_TYPES:
                raise ValidationError(
                    f"Statement type '{stmt_type}' is not allowed. Only SELECT queries are permitted."
                )
            # Any unknown/future statement type - reject by default (allowlist approach)
            raise ValidationError(
                f"Statement type '{stmt_type}' is not allowed. Only SELECT queries are permitted."
            )


def _get_cte_and_alias_names(statements: list) -> set[str]:
    """Collect CTE names and subquery aliases - these are not real tables."""
    virtual: set[str] = set()
    for stmt in statements:
        if stmt is None:
            continue
        for cte in stmt.find_all(exp.CTE):
            if cte.alias:
                virtual.add(str(cte.alias).lower())
        for alias in stmt.find_all(exp.TableAlias):
            if alias.this and hasattr(alias.this, "alias"):
                a = alias.this.alias
                if a:
                    virtual.add(str(a).lower())
            # Subquery alias: FROM (SELECT...) AS x -> the Table node has name x
            # TableAlias wraps the subquery; the alias might be on it
            if hasattr(alias, "alias") and alias.alias:
                virtual.add(str(alias.alias).lower())
    return virtual


def extract_table_refs(sql: str) -> list[TableRef]:
    """
    Extract all BigQuery table references from the SQL.
    Returns project.dataset.table style refs. CTEs and subquery aliases are excluded.
    """
    try:
        statements = sqlglot.parse(sql, dialect="bigquery")
    except Exception:
        return []

    virtual_tables = _get_cte_and_alias_names(statements)
    refs: list[TableRef] = []
    seen: set[tuple[str | None, str | None, str]] = set()

    for stmt in statements:
        if stmt is None:
            continue
        for table_node in stmt.find_all(exp.Table):
            catalog = table_node.catalog
            db = table_node.db
            name = table_node.name

            proj = catalog if (catalog and str(catalog).strip()) else None
            ds = db if (db and str(db).strip()) else None

            # Skip CTEs and subquery aliases (no catalog/db, and name in virtual set)
            if name and not proj and not ds and name.lower() in virtual_tables:
                continue

            if name and (proj or ds):
                key = (proj, ds, name)
                if key not in seen:
                    seen.add(key)
                    refs.append(TableRef(project=proj, dataset=ds, table=name))
            elif name and (proj or ds or name.lower() not in virtual_tables):
                key = (proj, ds, name)
                if key not in seen:
                    seen.add(key)
                    refs.append(TableRef(project=proj, dataset=ds, table=name))

    return refs
