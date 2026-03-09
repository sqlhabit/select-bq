# select-bq

A **SELECT-only BigQuery CLI wrapper** for agentic use (e.g. with Cursor). Wraps the official `bq` CLI and enforces:

- **SELECT-only**: Queries are validated via SQL AST parsing—no DML, DDL, scripting, `EXECUTE IMMEDIATE`, or hidden CTEs that could modify data.
- **Allowlist**: Optional config restricts queries to specific project/dataset/table. Empty or missing allowlist = no restriction.
- **Audit logging**: All queries (including rejections) are logged to a YAML file with timestamps.

## Install

```bash
pip install select-bq
```

Requires the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`bq` CLI) and `gcloud auth login`.

## Setup

Create a config file `.select-bq.yaml` in your project root:

```yaml
# Where to log queries (default: select-bq-queries.yaml in current dir)
log_path: select-bq-queries.yaml

# Optional allowlist. Omit or leave empty to allow all tables.
# When present, only these tables can be queried.
allowlist:
  - project: my-gcp-project
    dataset: analytics
    table: events
  - project: my-gcp-project
    dataset: analytics
    table: "*"   # wildcard: all tables in this dataset
```

- **`log_path`** — Path for the query log (default: `select-bq-queries.yaml`). Use an absolute path to log outside the project.
- **`allowlist`** — List of allowed `project`/`dataset`/`table`. Use `table: "*"` for all tables in a dataset. Omit to allow all tables.

To use a different config path: `select-bq query --config ./my-config.yaml "SELECT 1"`.

To use an external allowlist file:

```yaml
log_path: select-bq-queries.yaml
allowlist_path: allowlist.yaml
```

## Usage

```bash
# Run a SELECT query (same as bq query, but validated)
select-bq query "SELECT 1"
select-bq query "SELECT * FROM project.dataset.table LIMIT 10" --format=pretty

# Query from file
select-bq query -f query.sql

# Custom config
select-bq query --config ./my-config.yaml "SELECT * FROM my_table"

# Use Standard SQL (default) or legacy SQL
select-bq query --use_legacy_sql=false "SELECT 1"
select-bq query --use_legacy_sql=true "SELECT 1"

# All bq query flags are passed through (format, project_id, etc.)
select-bq query --format=pretty --project_id=my-project "SELECT 1"
```

## Query Log

Logged to `log_path` (default `select-bq-queries.yaml`):

```yaml
queries:
  - timestamp: "2025-03-09T12:00:00.000000+00:00"
    query: "SELECT 1"
    success: true
  - timestamp: "2025-03-09T12:01:00.000000+00:00"
    query: "INSERT INTO t VALUES (1)"
    success: false
    error: "Statement type 'Insert' is not allowed. Only SELECT queries are permitted."
```

## Security

- **AST parsing**: Uses [sqlglot](https://github.com/tobymao/sqlglot) with BigQuery dialect. Only `SELECT` statements are allowed; `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `EXECUTE IMMEDIATE`, `DECLARE`, `SET`, and similar are rejected.
- **Allowlist**: When configured, only tables matching the allowlist can be queried. Supports wildcards (`table: "*"` for all tables in a dataset).
- **No eval/exec**: Validation is purely structural—no dynamic execution of user input.

## Cursor Integration

Add to your project's Cursor rules or AGENTS.md:

```markdown
Use `select-bq query "SELECT ..."` when querying BigQuery. Do not use raw `bq` for queries.
```

## Publishing

To build and publish to PyPI:

```bash
pip install build twine
python -m build
twine upload dist/*
```
