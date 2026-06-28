# AGENTS.md

## Runtime
- Use `uv`; the repo has `uv.lock` and targets Python `3.12` (`.python-version`, `pyproject.toml`).
- Install or sync deps with `uv sync`.

## Entry Points
- The real app entrypoint is the Typer CLI in `src/wv/cli/main.py`.
- Console scripts are `wv` and `wildlife-vision` (`pyproject.toml`), so the primary smoke test is `uv run wv --help`.
- Do not treat the repo-root `main.py` as application code; it is just a placeholder that prints `Hello from wildlife-vision!`.

## Repo Shape
- `src/wv/cli/commands/` defines the CLI surface only.
- `src/wv/use_cases/` is the intended home for command logic.
- `src/wv/core/` holds shared filesystem / image / EXIF helpers.
- `src/wv/config/__init__.py` loads package-local config from `src/wv/config/setup.yml`.

## Current State
- Most CLI commands are scaffolds that return `None`; do not assume the CLI is fully wired to `use_cases` yet.
- `src/wv/use_cases/ingest/sd.py` is the only use case with meaningful in-progress logic at the moment.

## Config Gotcha
- `wv.config.load()` is `@lru_cache`d. If code edits `src/wv/config/setup.yml` and needs fresh values in the same process, clear the cache or start a new process.

## Verification
- There is currently no `tests/` tree, no CI workflow, and no configured lint/typecheck tooling in the repo.
- For small changes, verify with focused CLI checks such as `uv run wv --help` or subcommand help like `uv run wv ingest sd --help`.
