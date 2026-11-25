# Contributing to Kosmos

Thank you for helping improve Kosmos. The project is source-available under the PolyForm
Noncommercial License 1.0.0; submitting a contribution does not change that license.

## Before contributing

Read [AGENTS.md](AGENTS.md), the [architecture overview](docs/architecture/README.md), and the
[development guide](docs/development/README.md). Open an issue before substantial or architectural
work so scope, security, licensing, and roadmap fit can be discussed.

The project intends to preserve the option of future commercial licensing. A Contributor License
Agreement may therefore be introduced after legal and maintainer review. No CLA is currently in
force and no automated acceptance is configured. See the non-binding
[CLA strategy proposal](docs/legal/CONTRIBUTOR-LICENSE-STRATEGY.md).

## Development workflow

1. Branch from `develop` using `feature/*`, `fix/*`, `docs/*`, `refactor/*`, or `chore/*`.
2. Keep changes focused and avoid unrelated formatting or dependency updates.
3. Add or update tests and documentation for behavior changes.
4. Run the required checks:

   ```bash
   uv sync --frozen --dev
   uv run ruff check .
   uv run ruff format --check .
   uv run pytest
   ```

5. Use English Conventional Commits and open a pull request to `develop`.
6. Integrate only with a merge commit after all required CI checks pass. Squash merges and rebase
   merges are not allowed.
7. Delete an eligible temporary branch after its pull request is merged. Never delete the
   permanent `main` or `develop` branches.

Release and hotfix flows will be activated only when the project has delivered versions. The
`main` and `develop` branches are permanent; do not delete or force-push them.

## Pull requests

Explain the problem, approach, tests, security and privacy impact, dependency or licensing impact,
and documentation changes. Keep pull requests reviewable. Required CI checks must pass, review
feedback must be resolved, and new dependencies require a licensing review. Use the repository's
merge-commit strategy; do not squash or rebase a pull request during integration.

## Code and documentation standards

- Use English throughout new project material.
- Target Python 3.12 and the configured 100-character line limit.
- Prefer clear code and concrete boundaries over speculative abstractions.
- Never claim roadmap functionality is implemented before validation.
- Never include credentials, private data, model files, recordings, or generated local state.
- Do not modify approved visual identity artifacts without explicit approval and hash validation.

## Conduct and security

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Do not disclose suspected
vulnerabilities in a public issue; follow [SECURITY.md](SECURITY.md).
