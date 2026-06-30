# AGENTS.md

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
- `src/wv/cli/runtime.py` and `src/wv/cli/presentation.py` own terminal logging, Rich summaries, and future progress plumbing.
- `src/wv/core/` holds shared filesystem / image / EXIF / metadata helpers.
- `src/wv/config/__init__.py` loads package-local config from `src/wv/config/setup.yml`.

## Current State
- Implemented command paths worth verifying are `setup`, `ingest sd`, `detect content`, and `clean {corrupted,overexposed-ir,bursts}`.
- `ingest folder` and `pipeline preprocess` are still placeholders; `src/wv/cli/commands/export.py` exists but is not registered in the root app.
- `wv setup` calls MegaDetector model preparation (`src/wv/use_cases/setup.py`, `src/wv/ml/megadetector.py`) and can trigger model resolution/download, so prefer help or tests for routine smoke checks.

## Config Gotcha
- `wv.config.load()` is `@lru_cache`d. If code edits `src/wv/config/setup.yml` and needs fresh values in the same process, clear the cache or start a new process.
- `paths.root` defaults to `./.wv`; `ingest sd` writes sessions under `.wv/sessions/<timestamp>__<device>/initial`.
- Device IDs and monitoring-site IDs come from `src/wv/config/setup.yml`; the CLI rejects unknown values.

## Verification
- There is a real `tests/` tree and `uv run pytest` currently passes.
- There is no repo-configured lint, formatter, typechecker, pre-commit, or CI workflow to run.
- Useful focused checks:
  - `uv run pytest`
  - `uv run pytest tests/cli`
  - `uv run pytest tests/use_cases/ingest/test_sd.py`
  - `uv run wv --help`
  - `uv run wv ingest sd --help`
- `tests/conftest.py` resets config caches and the CLI runtime singleton between tests; keep that fixture in sync if you add more global CLI state.
