# Security and Privacy Principles

Kosmos may eventually act on a user's computer, so security is an architectural constraint from the
first implementation stage.

- Grant the least privilege required for the current action.
- Represent intent separately from authorization and execution.
- Require explicit confirmation for sensitive or irreversible actions.
- Validate and constrain input at trust boundaries.
- Store credentials outside source control and minimize their lifetime and scope.
- Isolate integrations and external providers.
- Process locally by default and never send data silently.
- Make actions visible and logs useful without exposing unnecessary private data.
- Give users control over permissions, automations, and cancellation.
- Refuse automatic destructive command execution.

Future external-agent integrations must follow the same rules. This document states requirements;
Stage 00 does not implement an authorization system.
