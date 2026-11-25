# Security Policy

## Supported versions

Kosmos is in pre-alpha foundation development and has no released or supported production version.
Security fixes currently target the active development branches.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or include secrets, personal data, or
exploit details in public discussions.

A private security reporting channel has not yet been approved. This is a maintainer decision that
must be completed before public release. Until then, do not send sensitive vulnerability details
through an unverified channel. Repository maintainers should enable GitHub private vulnerability
reporting or publish a dedicated security contact, then update this file.

When a private channel is available, include affected components, reproduction conditions, impact,
and any suggested mitigation. Do not access data that is not yours, disrupt services, or perform
destructive testing.

## Security principles

Kosmos is designed around least privilege, explicit authorization for sensitive actions, separation
of intent from execution, input validation, credential protection, integration isolation, local
processing by default, transparent actions, privacy-conscious logs, user-controlled permissions,
cancellable operations, and no silent external data transmission or destructive command execution.

These are design requirements, not claims that a security subsystem is implemented in Stage 00.
