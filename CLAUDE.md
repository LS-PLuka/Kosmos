# Claude Code Guidance

Read and follow [AGENTS.md](AGENTS.md) as the authoritative engineering guide for Kosmos.

Claude Code must also:

- inspect the repository and relevant files before proposing edits;
- review structure and readability in addition to running automated formatters and tests;
- preserve the documented domain boundaries, provider independence, and modular-monolith
  dependency direction;
- keep local processing primary and require explicit authorization for external data transfer;
- preserve the separation of AI intent interpretation from deterministic validation,
  authorization, and execution;
- keep tool permissions narrow and ask before destructive or external actions;
- use the configured uv, Ruff, and Pytest commands rather than inventing parallel workflows;
- keep delivery incremental and never advance to another roadmap stage without authorization;
- leave commits, pushes, pull requests, merges, rebases, force pushes, tags, releases, and branch
  deletion to the maintainer;
- preserve approved branding artifacts byte-for-byte unless explicitly asked to change them; and
- review and test every change, then report commands run, results, limitations, and unvalidated
  assumptions.

Do not duplicate or override the architecture, licensing, security, Git, or roadmap rules in
`AGENTS.md`.
