# Third-Party Notices

This file records third-party components incorporated into or required to develop the current
repository. External runtime software and model weights are listed separately and are not
incorporated into Kosmos. Planned external intelligence providers and web, voice, and desktop
technologies remain excluded until their corresponding implementation and licensing review.

## Python runtime dependencies

| Component | Resolved version | Purpose | License |
| --- | --- | --- | --- |
| HTTPX | 0.28.1 | Asynchronous Ollama HTTP client | BSD-3-Clause |
| HTTPCore | 1.0.9 | HTTPX transport layer | BSD-3-Clause |
| AnyIO | 4.16.0 | HTTPX asynchronous compatibility layer | MIT |
| Certifi | 2026.11.20 | TLS certificate authority bundle | MPL-2.0 |
| h11 | 0.16.0 | HTTP/1.1 protocol implementation | MIT |
| idna | 3.20 | Internationalized domain name handling | BSD-3-Clause |
| typing-extensions | 4.16.0 | Compatibility typing primitives | PSF-2.0 |

HTTPX is constrained to `>=0.28,<0.29` and supports Python 3.12. Versions above are the exact
resolution currently recorded in `uv.lock`. License expressions were checked against installed
package metadata and upstream project metadata on November 26, 2026.

## External local-inference requirements

Ollama 0.40.18 and Qwen 3.5 4B Q4_K_M are target-host runtime requirements. Neither the Ollama
binary nor model weights are distributed, downloaded, or installed by this repository. Ollama is
upstream MIT-licensed software. The exact license and acceptable-use terms for the selected Qwen
artifact must be verified by the maintainer before any redistribution; upstream presentation as
Apache-2.0 does not replace artifact-specific verification.

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
