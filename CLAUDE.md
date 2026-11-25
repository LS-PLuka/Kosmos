# Claude Code Guidance

Read and follow [AGENTS.md](AGENTS.md) as the authoritative engineering guide for Kosmos.

Claude Code must also:

- inspect the repository and relevant files before proposing edits;
- keep tool permissions narrow and ask before destructive or external actions;
- use the configured uv, Ruff, and Pytest commands rather than inventing parallel workflows;
- preserve approved branding artifacts byte-for-byte unless explicitly asked to change them; and
- report commands run, validation results, limitations, and any unvalidated assumptions.

Do not duplicate or override the architecture, licensing, security, Git, or roadmap rules in
`AGENTS.md`.
