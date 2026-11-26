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
uv lock --check
uv sync --frozen --dev
uv run ruff check .
uv run ruff format --check .
uv run pytest
git diff --check
```

Use `uv run ruff format .` to apply formatting. Ruff is configured for Python 3.12 and a
100-character line length. Pytest discovers tests under `tests` and treats unknown configuration or
markers as errors.

## Code quality and readability

Formatting is the baseline, not the complete review. For each changed Python file:

- use four spaces and never tabs; keep UTF-8, LF line endings, and a final newline;
- use double quotes and natural line breaks within the configured 100-character limit;
- group standard-library, third-party, and Kosmos imports, removing unused and wildcard imports;
- choose specific English names and preserve public contracts unless a change is approved;
- type public parameters, returns, and concrete boundaries with modern Python 3.12 syntax;
- keep functions and classes cohesive, nesting low, side effects visible, and exception handling
  specific;
- extract helpers only when they improve comprehension or reuse;
- explain only decisions, constraints, security, and non-obvious trade-offs in English comments or
  docstrings; and
- inspect responsibility, complexity, duplication, coupling, dependency direction, and
  maintainability after automated checks pass.

Tests receive the same review. Use descriptive names, focused fixtures, clear assertions, and
deterministic inputs. Arrange, Act, Assert separation is useful when it clarifies a scenario, but
should not add ceremonial comments. Automated tests must not depend on a GPU, Ollama, installed
models, credentials, network services, or corporate infrastructure.

## Cross-platform workflow

Ubuntu is the primary execution environment. Windows supports development and isolated testing for
portable behavior. Prefer fakes for internal contracts, mocks or simulated HTTP transports for
external integrations, and platform adapters only when actual operating-system differences exist.
Do not maintain separate complete implementations. Real local-model inference tests are manual or
integration-specific and remain outside the deterministic automated suite.

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
