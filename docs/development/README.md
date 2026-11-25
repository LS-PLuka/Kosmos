# Development Guide

## Requirements

- Git
- uv
- Python 3.12, managed by uv when desired

Install uv using the [official instructions](https://docs.astral.sh/uv/getting-started/installation/).
Then prepare the repository:

```bash
uv python install 3.12
uv sync --frozen --dev
```

`uv.lock` is authoritative for reproducible development and CI environments. Use `uv lock` only
when project dependencies intentionally change and include the resulting lockfile in review.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Use `uv run ruff format .` to apply formatting. Ruff is configured for Python 3.12 and a
100-character line length. Pytest discovers tests under `tests` and treats unknown configuration or
markers as errors.

## Package layout

Importable code lives under `src/kosmos`. Unit tests belong in `tests/unit`; tests exercising real
boundaries belong in `tests/integration`, and reusable test doubles belong in `tests/fakes`. Do not
add `__init__.py` files merely to populate planned domain directories. Stage 01.1 asynchronous
contract tests use `asyncio.run`, so no asynchronous Pytest plugin is required.

## Motion Lab

The approved visual prototype is self-contained. Open `tools/motion-lab/index.html`, or from the
repository root run `python -m http.server 8765 --bind 127.0.0.1` with a working Python interpreter
and visit `http://localhost:8765/tools/motion-lab/`. Optional regression dependencies are described
in `docs/branding/PACKAGE-README.pt-BR.md`; they are not project dependencies.
