# Decisions log
| # | Date | Decision | Why |
|---|------|----------|-----|
| 1 | 2026-09-01 | File-IPC bridge, not TCP/SDK, for v1 | Proven by vwx-mcp + randneto; no SDK build; crash-proof |
| 2 | 2026-09-01 | Read-only tools ship first | Safety; mutation gated behind saved-doc + named undo |
| 3 | 2026-09-01 | Primary target VW 2026 Win; min 2025 | CC_* source/dest tracing needs 2025+ |
