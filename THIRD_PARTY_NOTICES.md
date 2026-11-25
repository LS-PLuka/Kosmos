# Third-Party Notices

This file records third-party components incorporated into or required to develop the current
repository. Planned technologies are not current dependencies and are not listed as incorporated.

## Python development tooling

| Component | Purpose | License |
| --- | --- | --- |
| Hatchling | Python build backend | MIT |
| Pytest | Automated testing | MIT |
| Ruff | Linting and formatting | MIT |
| uv | Environment and dependency management | Apache-2.0 OR MIT |

The exact resolved development dependency versions are recorded in `uv.lock`; the build backend is
resolved under the constraint in `pyproject.toml`. These tools retain their upstream licenses and
notices; the Kosmos license does not replace them.

## Continuous integration

| Component | Purpose | License |
| --- | --- | --- |
| actions/checkout | GitHub Actions repository checkout | MIT |
| astral-sh/setup-uv | uv installation in GitHub Actions | MIT |

## Community standards

`CODE_OF_CONDUCT.md` is adapted from Contributor Covenant version 2.1, licensed under CC BY 4.0.

## Branding toolchain context

The Motion Lab uses native browser APIs and includes no third-party JavaScript library. Optional
export and regression tools named in `docs/branding/LICENSES.md` are not bundled dependencies. No
font files are incorporated. Space Grotesk, Inter, and JetBrains Mono are visual references only.

License identifiers above are informational and should be verified against the exact version and
upstream notice before any distribution decision. This document is not legal advice.
