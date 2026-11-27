# Third-Party Notices

This file records third-party components incorporated into or required to develop the current
repository. External runtime software and model weights are listed separately and are not
incorporated into Kosmos. Planned external intelligence providers and later-stage voice, web, and
desktop technologies remain excluded until their corresponding implementation and licensing
review.

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
| SoundDevice | 0.5.6 | Optional local PCM audio and PortAudio adapter | MIT |
| CFFI | 2.1.1 | Optional SoundDevice foreign-function interface | MIT |
| pycparser | 3.12 | Optional CFFI parser dependency | BSD-3-Clause |

HTTPX is constrained to `>=0.28,<0.29` and supports Python 3.12. Versions above are the exact
resolution currently recorded in `uv.lock`. License expressions were checked against installed
package metadata and upstream project metadata on November 26, 2026.

SoundDevice is constrained to `>=0.5.6,<0.6` in the optional `voice` extra and supports Python 3.12.
Its Windows wheels include PortAudio binaries under the PortAudio license, which permits use and
redistribution with its copyright and permission notice. Linux installations use the system
PortAudio shared library, which this repository does not distribute. SoundDevice, CFFI, and
pycparser versions above are the exact optional resolution in `uv.lock`; their upstream metadata
and licenses were checked on November 27, 2026.

## External local-inference requirements

Ollama 0.40.18 and Qwen 3.5 4B Q4_K_M are target-host runtime requirements. Neither the Ollama
binary nor model weights are distributed, downloaded, or installed by this repository. Ollama is
upstream MIT-licensed software. The exact license and acceptable-use terms for the selected Qwen
artifact must be verified by the maintainer before any redistribution; upstream presentation as
Apache-2.0 does not replace artifact-specific verification.

## External optional text-to-speech components

Piper 1.8.0 is an optional independently installed local runtime licensed GPL-3.0-or-later. Kosmos
invokes its documented CLI through an external-process adapter but does not import, incorporate,
download, or distribute Piper. The reviewed release supports Python 3.12 and publishes Windows
x86-64 and Linux x86-64/aarch64 ABI3 wheels. The external-process boundary is not an automatic
legal compatibility guarantee; joint distribution requires additional review.

`Lucasllfs/Razo-piper-voice` is the provisional external Brazilian Portuguese voice. Its repository
declares MIT and publishes an ONNX SHA-256, but does not fully document the dataset source,
recording license, fine-tune ancestry, speaker consent, or voice rights. Kosmos does not download or
distribute the model. Local testing does not establish redistribution rights. The model must remain
external and provisional until provenance, rights, and distribution review is complete.

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

## Speech recognition

The optional `stt` extra directly resolves Faster Whisper 1.2.1 (MIT) and NumPy 2.5.5
(BSD-3-Clause). Faster Whisper resolves CTranslate2 4.9.1 (MIT), PyAV 19.0.2 (BSD-3-Clause),
Hugging Face Hub 2.5.0 (Apache-2.0), Tokenizers 0.23.3 (Apache-2.0), ONNX Runtime 1.32.0 (MIT),
tqdm 4.70.1 (MIT and MPL-2.0), PyYAML 6.0.4 (MIT), protobuf 7.36.2 (BSD-3-Clause), and flatbuffers
25.12.19 (Apache-2.0), plus support packages recorded in `uv.lock`. PyAV wheels include FFmpeg
libraries whose enabled components and licenses must be inspected for each distributed wheel; the
PyAV license alone does not describe every native component.

The external `Systran/faster-whisper-base` reference model at revision
`ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66` declares MIT and is not downloaded, incorporated, or
distributed by Kosmos. The original OpenAI Whisper model card and converted-model provenance remain
part of the pre-distribution review. Local hashes demonstrate file identity only. These notices do
not assert absolute legal compatibility with Kosmos or replace review of exact upstream artifacts.

## Voice activity detection

The optional `vad` extra directly resolves ONNX Runtime 1.32.0 (MIT) and NumPy 2.5.5
(BSD-3-Clause). ONNX Runtime resolves flatbuffers 25.12.19 (Apache-2.0), packaging 26.4
(Apache-2.0 OR BSD-2-Clause), and protobuf 7.36.2 (BSD-3-Clause), as recorded in `uv.lock`.
Exact native runtime notices and the contents of each distributed wheel require artifact-specific
review.

The selected external model is Silero VAD v6.2.3 `silero_vad.onnx` at revision
`5cd7945676eb32225748052e2e6a0580e4686a08`. The upstream repository license is MIT, and the
maintainer explicitly answered that MIT applies to this model file in discussion 817. The cited
SHA-256 is `1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3`, and byte-identical
mirrors report 2,327,524 bytes. Kosmos does not download, incorporate, or distribute the model;
these values were not locally verified in this implementation. Any future distribution must
preserve the Silero copyright and MIT permission notice and repeat exact-artifact review.
