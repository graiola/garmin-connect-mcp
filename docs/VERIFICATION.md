# Verification record

## Current local verification — November 5, 2026

- Python 3.12.14 / Linux, with project and development dependencies installed
  into an isolated `.venv`.
- `.venv/bin/python -m pytest -q`: **78 passed** (0.87 seconds).
- `.venv/bin/python -m compileall -q src`: passed.
- `bash -n scripts/publish_github.sh scripts/tunnel_stdio.sh`: passed.
- `git diff --check`: passed.
- The project documentation was made English-only and the icon added to the README.
- Set `asyncio_default_fixture_loop_scope = "function"` explicitly to keep tests
  compatible with current pytest-asyncio while treating warnings as errors.
- The GitHub repository was confirmed to exist as **public**, on `master`.
  Publication of source code does not verify a running MCP service.

## Original development verification

- Python 3.13.5 / Linux.
- `python -m pytest -q`: **78 passed** (final rerun: 4.69 seconds).
- `python -m compileall -q src`: passed.
- `bash -n scripts/publish_github.sh scripts/tunnel_stdio.sh`: passed.
- Offline wheel build and install into an isolated target: passed; CLI discovers 6 tools.
- Publication script invoked in the original development environment: stopped
  safely with `Install gh locally first`, exit 1; no remote repository was created
  **during that earlier run**.
- Unit/contract tests: Garmin paths and params, raw-JWT token exchange, renewal,
  single refresh on 401, concurrent exchange deduplication, retry limits,
  malformed/oversized responses, no redirects/remote URL selection, no data writes.
- Privacy: key not in repr or diagnostics; protected files and explicit source
  precedence; structured GPS/identity filtering without changing numeric values.
- MCP: initialize/tool discovery/tool calls, structured and text results, invalid
  inputs, readonly annotations, and no accidental execution from notifications.
- Local HTTP: authentication, Host/Origin checks, size/version/content handling,
  notifications 202, GET/DELETE 405 and complete mocked tool call.
- Actual stdio subprocess handshake, discovery and status call (no Garmin network).

Tests use **synthetic data only**. This is not validation of real API responses.
The environment could not download additional packages, so interoperability against
an independently installed MCP SDK/Inspector was not executed; protocol tests use
the published contract. The project does not require an MCP SDK at runtime.

## Not executed / not claimed

- A live Garmin call with the user's Personal API key.
- Coverage of the user's strength sets, corrected exercise names and pool intervals.
- OpenAI tunnel creation or authenticated ChatGPT tool invocation.
- Docker image build/run.
- CI execution on GitHub or Python 3.11.
- Live endpoint deployment or an authenticated ChatGPT tool invocation; a public
  GitHub source repository is not a deployed MCP endpoint.

## Local host acceptance checklist

1. Install dependencies and rerun all tests.
2. Run `configure` locally, then `doctor`; do not paste the key into chat.
3. Fetch one representative activity and compare to Garmin Connect.
4. Check the associated-workouts response; do not assume executed sets are present.
5. Verify weight units, a date range, and one empty-data case.
6. Review the existing public GitHub repository and check CI after source updates.
7. Configure the official private tunnel and confirm readiness.
8. Add the private MCP connection in ChatGPT, perform a real read and verify its data.
9. Test restart and key revocation/rotation without exposing secret values.

Only steps actually completed may be marked complete. A green mock suite alone
must not be described as a live Garmin/ChatGPT connection.
