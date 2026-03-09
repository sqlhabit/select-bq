# safe-bq

A **safe BigQuery CLI wrapper** for agentic use (e.g. with Cursor). Wraps the official `bq` CLI and enforces:

- **SELECT-only**: Queries are validated via SQL AST parsing—no DML, DDL, scripting, `EXECUTE IMMEDIATE`, or hidden CTEs that could modify data.
- **Allowlist**: Optional config restricts queries to specific project/dataset/table. Empty or missing allowlist = no restriction.
- **Audit logging**: All queries (including rejections) are logged to a YAML file with timestamps.

## Install

From PyPI:

```bash
pip install safe-bq
# or
uv pip install safe-bq
```

From source (development):

```bash
pip install -e .
uv pip install -e .
```

Requires the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`bq` CLI) and `gcloud auth login`.

## Configuration

Create a config file `.safe-bq.yaml` in your project root (or use `--config` to point to another path). You can copy from `.safe-bq.example.yaml` in this repo.

### Log file

Set where queries are logged with `log_path`:

```yaml
log_path: safe-bq-queries.yaml   # default if omitted
# or e.g.:
log_path: /var/log/safe-bq/queries.yaml
```

### Allowlist

To restrict which tables can be queried, add an `allowlist`. If the allowlist is present and non-empty, only tables matching it are allowed. Omit it or leave it empty to allow all tables.

**Inline allowlist** (in `.safe-bq.yaml`):

```yaml
log_path: safe-bq-queries.yaml

allowlist:
  - project: my-project
    dataset: my_dataset
    table: my_table
  - project: other
    dataset: analytics
    table: "*"   # wildcard: all tables in this dataset
```

**External allowlist file** (useful to share across projects):

```yaml
log_path: safe-bq-queries.yaml
allowlist_path: allowlist.yaml
```

Then create `allowlist.yaml`:

```yaml
allowlist:
  - project: my-project
    dataset: my_dataset
    table: my_table
```

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

## Publishing

To build and publish to PyPI:

```bash
pip install build twine
python -m build
twine upload dist/*
```
