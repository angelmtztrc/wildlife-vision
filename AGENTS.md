# AGENTS.md

## While implementing

When developing or implemeting features, always make sure to review the codebase to align with the way the project is writen or structured. Don't duplicate code, always review what does exist in the /core folder. If something is used in several places maybe it can worth moving it to the core.

## Asking

When you're giving the order to define a plan, always ask for whatever information is needed, and confirm anything that may feel uncertain.

## Runtime

- Use `uv`; the repo has `uv.lock` and targets Python `3.12` (`.python-version`, `pyproject.toml`).
- Install deps with `uv sync`; include tests with `uv sync --group dev`.

## Entry Points

- The real app entrypoint is the Typer CLI in `src/wv/cli/main.py`.
- Console scripts are `wv` and `wildlife-vision` (`pyproject.toml`). Use `uv run wv --help` as the basic smoke test.
- Do not treat the repo-root `main.py` as application code; it is just a placeholder that prints `Hello from wildlife-vision!`.
- The global `--verbose` flag lives on the root app, so it must come before the subcommand: `uv run wv --verbose setup`.

## Repo Shape

- `src/wv/cli/commands/` defines the CLI surface only.
- `src/wv/use_cases/` is the intended home for command logic.
- `src/wv/core/` holds shared filesystem / image / EXIF / metadata helpers plus the Rich-backed logger in `src/wv/core/logger.py`.
- `src/wv/config/__init__.py` loads package-local config from `src/wv/config/setup.yml`.

## Core Documentation

- Every function in `src/wv/core/` that is reusable across the project must have a Google-style docstring.
- Document behavior, arguments, return values, raised exceptions, side effects, fallback behavior, and important constraints when they apply.
- File-private helpers and framework override methods do not need function docstrings. Internal adapters should have concise class-level documentation instead.

## Persistence Architecture

- Use `SQLAlchemy` ORM models only for database persistence concerns.
- Keep ORM entities inside `src/wv/persistence/models/`; they must not leak into CLI or use-case layers.
- Use class-based repositories in `src/wv/persistence/repositories/` for database access.
- Repositories must accept a `SqlSession` (the local name for SQLAlchemy's `Session`) and return application dataclasses, not ORM entities.
- Use `SqlSession` as the transaction and unit-of-work boundary.
- Top-level use cases should own the SQL session lifecycle for their work; repositories should never create their own SQL sessions.
- Do not use raw `sqlite3` for application persistence. Prefer the shared SQLAlchemy persistence stack.

## Data Boundaries

- Use dataclasses for use-case inputs, outputs, domain values, and internal events.
- Do not define application-facing result types inside persistence modules.
- Prefer boundary-correct names like `Device`, `MonitoringSite`, and `Deployment` instead of persistence-oriented `*Record` names.
- Keep Pydantic models for FastAPI request/response schemas only; do not use them as persistence or domain models.

## Migrations

- Use `Alembic` as the source of truth for schema migrations.
- Do not add new hand-rolled SQL migration runners.
- Keep `initialize_database(...)` as the application bootstrap entrypoint, but have it apply Alembic migrations programmatically.
- Use standard Alembic version tracking.

## Implementation Notes

- Preserve clear separation:
  - CLI -> use cases
  - use cases -> repositories
  - repositories -> SQLAlchemy models/SqlSession
- Avoid leaking ORM behavior into business logic.
- When adding persistence-backed features, first check whether an existing repository or domain dataclass should be extended instead of creating parallel patterns.

## Current State

- Implemented command paths worth verifying are `setup`, `ingest {sd,folder}`, `pipeline preprocess`, `detect content`, and `clean {corrupted,overexposed-ir,bursts}`.
- `src/wv/cli/commands/export.py` exists but is not registered in the root app.
- `wv setup` calls MegaDetector model preparation (`src/wv/use_cases/setup.py`, `src/wv/ml/megadetector.py`) and can trigger model resolution/download, so prefer help or tests for routine smoke checks.

## Config Gotcha

- `src/wv/config/setup.yml` is deprecated and retained only for compatibility with older tests; ingest does not read it.
- Ingest requires the active workspace configured globally. Sessions are written under `<workspace>/sessions/<timestamp>__<device>/init`.
- `ingest sd` reads device and monitoring-site IDs from `<sd>/.wv/config.yml`; `ingest folder` receives them as options. Both validate IDs against the active workspace database.

## Logging

- CLI commands now log through `wv.core.logger`, not a CLI-specific runtime layer.
- `logging.Logger.done(...)` is added dynamically in `src/wv/core/logger.py`; runtime is fine, but type checkers will treat `get_logger()` as returning a plain `logging.Logger` unless you add typing support.
- `tests/conftest.py` uses `wv.core.logger.reset_logging()` plus config cache clears to isolate CLI tests; keep that fixture in sync if you add more logger globals.
- Use `INFO` for user-facing milestones, `DEBUG` for per-item/process detail, `WARN` for non-blocking anomalies, `ERROR` for failures that make a file or step fail, and `DONE` for command completion only.
- Long-running use cases should prefer `wv.core.logger.get_progress()` instead of extra `INFO` chatter.
- Use `wv.core.display.display_file()` / `display_path()` in logs so paths stay readable.
- Avoid high-volume `INFO` logs for expected per-file work; if a message only helps diagnose behavior, keep it at `DEBUG`.

## Verification

- There is a real `tests/` tree and `uv run pytest` currently passes.
- There is no repo-configured lint, formatter, typechecker, pre-commit, or CI workflow to run.
- Useful focused checks:
  - `uv run pytest`
  - `uv run pytest tests/cli`
  - `uv run pytest tests/use_cases/ingest/test_sd.py`
  - `uv run wv --help`
  - `uv run wv ingest sd --help`
