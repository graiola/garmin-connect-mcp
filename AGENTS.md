# Development instructions

Keep this connector small, read-only, and explicit. No Garmin web scraping or
password/session login. Do not introduce arbitrary URL fetching or remote writes.
Do not store credentials, FIT exports, personal measurements or live fixtures in git.

Before changing endpoint paths or payload assumptions, check the official Garmin
Personal API contract and cite the source in docs/API_CONTRACT.md. Avoid unsupported
claims about per-set strength data. Preserve raw units and field meaning.

Run `python -m pytest -q`, `python -m compileall -q src` and shell syntax checks.
Update docs/VERIFICATION.md with what actually ran. A passed mock suite is not a
live acceptance test. Never report a push/deployment/connection without evidence.
MCP extensions must add contract tests and truthful capabilities/annotations.

Do not broaden public networking or authentication casually. The HTTP mode is
local-only, with a separate bearer token. Prefer the authenticated private tunnel.
