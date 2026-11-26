# Security and Privacy Principles

Kosmos may eventually act on a user's computer, so security is an architectural constraint from the
first implementation stage.

- Grant the least privilege required for the current action.
- Deny execution by default when authorization is absent.
- Represent intent separately from authorization and execution.
- Require explicit confirmation for sensitive or irreversible actions.
- Validate arguments and constrain time, calls, iterations, and other execution resources.
- Store credentials outside source control and minimize their lifetime and scope.
- Isolate integrations and external providers.
- Process locally by default and never send data or fall back to a remote provider silently.
- Make actions visible and logs useful without exposing unnecessary private data.
- Give users control over permissions, automations, and cancellation.
- Prohibit unrestricted terminal or operating-system access by an LLM.
- Refuse automatic destructive command execution.

Local-first does not mean local-only. Remote providers and specialized agents may be used only as
optional, configurable integrations with appropriate authorization and clear disclosure. Product
subscriptions do not imply programmatic access, unlimited availability, or permission to use an
unofficial integration mechanism.

Internet content is untrusted data. It cannot authorize an operation or override Kosmos policy.
Future web tooling must defend against prompt injection, avoid exposing personal data, distinguish
facts from inference, and preserve source references. A self-hosted search frontend may still send
queries to external search engines and must disclose that boundary.

Future external-agent integrations must follow the same rules. This document states architectural
requirements; Stage 01.1 does not implement a complete authorization system.

## In-memory conversation boundary

The Stage 01.3 Conversation Engine retains confirmed message pairs only in process memory and keeps
session histories isolated. It performs no automatic persistence, logging of message content,
remote fallback, tool execution, or additional transmission beyond the explicitly injected
provider call. Clearing or deleting a session removes managed references but does not guarantee
physical memory erasure. The engine is not a complete retention, secure-erasure, or multi-process
isolation system.

## Personality instruction boundary

The Stage 01.4 Personality Engine builds instructions only from validated structured configuration.
It does not accept conversation messages, retrieved content, tool results, or other untrusted text
as system instructions. It performs no persistence, logging, network access, tool execution,
authorization, or command execution.

Behavioral instructions are guidance to a language model, not an enforcement boundary. They do
not establish prompt-injection resistance or guarantee that a small model will comply. Kosmos
must continue to validate and authorize operations in deterministic software and may claim an
action or result only when reliable evidence is available.

## Local Ollama boundary

The Stage 01.2 adapter accepts only HTTP(S) loopback endpoints without credentials, queries,
fragments, or paths. Its HTTP client ignores proxy and certificate environment variables, does not
follow redirects, and preserves normal TLS certificate verification for HTTPS. The adapter uses
only fixed Ollama API paths and has no remote fallback, telemetry, shell execution, or automatic
model download.

Loopback transport alone does not prove offline inference. Operators requiring exclusively local
execution must start Ollama with `OLLAMA_NO_CLOUD=1` and verify the installed model artifact and
service configuration. Kosmos does not change the host's Ollama configuration.
