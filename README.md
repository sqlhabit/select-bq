# safe-bq

A **safe BigQuery CLI wrapper** for agentic use (e.g. with Cursor). Wraps the official `bq` CLI and enforces:

- **SELECT-only**: Queries are validated via SQL AST parsing—no DML, DDL, scripting, `EXECUTE IMMEDIATE`, or hidden CTEs that could modify data.
- **Allowlist**: Optional config restricts queries to specific project/dataset/table. Empty or missing allowlist = no restriction.
- **Audit logging**: All queries (including rejections) are logged to a YAML file with timestamps.

## Install

```bash
pip install -e .
# or
uv pip install -e .
```

Requires the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`bq` CLI) and `gcloud auth login`.

## Usage

```bash
# Run a SELECT query (same as bq query, but validated)
safe-bq query "SELECT 1"
safe-bq query "SELECT * FROM project.dataset.table LIMIT 10" --format=pretty

# Query from file
safe-bq query -f query.sql

# Custom config
safe-bq query --config ./my-config.yaml "SELECT * FROM my_table"

# All bq query flags are passed through
safe-bq query --use_legacy_sql=false --project_id=my-project "SELECT 1"
```

## Config

Config file: `.safe-bq.yaml` (or `--config` path).

```yaml
# Where to log queries (default: safe-bq-queries.yaml)
log_path: safe-bq-queries.yaml

# Optional allowlist. If present and non-empty, ONLY these tables are allowed.
# No allowlist or empty = no table restriction.
allowlist:
  - project: my-project
    dataset: my_dataset
    table: my_table
  - project: other
    dataset: analytics
    table: "*"   # all tables in dataset
```

Or use a separate allowlist file:

```yaml
log_path: safe-bq-queries.yaml
allowlist_path: allowlist.yaml
```

## Query Log

Logged to `log_path` (default `safe-bq-queries.yaml`):

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
Use `safe-bq query "SELECT ..."` when querying BigQuery. Do not use raw `bq` for queries.
```
