# Verification record

## Simplified onboarding — November 6, 2026

Version 0.2.0 adds guided local setup and configuration export; it does not add
Garmin data endpoints, new remote permissions, OAuth, or public hosting.

- Python 3.12.14 / Linux, using the existing isolated project test environment.
- Full combined suite: **241 passed**. This includes the previous 164 tests,
  66 onboarding unit cases, ten independent subprocess cases, and one package
  version consistency check.
- New coverage: first setup, idempotent reuse, explicit source precedence,
  environment-only credentials, hidden-input failure/cancellation, probe-before-save,
  failed-rotation preservation, exclusive/atomic publication, target-change checks,
  private permissions, source overrides, sanitized filesystem errors, and HTTP
  credentials excluded from stdio/setup/doctor.
- All three generated formats (common JSON, VS Code JSON, Codex TOML) were parsed
  and used to launch actual stdio subprocesses for initialization, six-tool
  discovery, and local status. Child DNS and outbound sockets were blocked, with
  only synthetic key files and a minimal allowlisted environment.
- Independent checks found and fixed version drift in MCP initialization/status
  and TOML escaping for DEL. Tests also cover spaces, quotes, non-BMP Unicode,
  preservation of the virtualenv interpreter path, and rejection of undecodable
  filename bytes. These are process-level checks, not actual client-app acceptance.
- `python -m compileall -q src scripts`, shell syntax checks, and `git diff --check`
  passed. The six tool schemas still match the unchanged distribution snapshot.
- The updated companion passed the skill validator. A fresh-context exercise
  explained Ubuntu/Python 3.10 onboarding, Cursor configuration, automatic token
  renewal versus key expiry, and the separate browser-ChatGPT tunnel prerequisite
  without installing software or collecting credentials.
- Package validation and two independent builds passed and produced identical
  bytes. Version 0.2.0 upload archive: **32,518 bytes**, SHA-256
  `b241bc15b8e4fe90caf4699171b558700d8bff2ec11c0a58139a003a1e38c663`.
- An isolated **offline** uv installation was attempted locally, but could not
  resolve `httpx` because its package was not cached. This was not a completed
  clean installation. CI now includes an isolated uv install from the checkout
  using Python 3.12, CLI version output, and all three configuration formats;
  check the matching GitHub Actions run for its actual execution result.
- Publication [CI run 42195513838](https://github.com/graiola/garmin-connect-mcp/actions/runs/42195513838)
  for source commit `0bd870c230a63366486f3cb8fd550ed50a79a3b5` subsequently passed
  on Python 3.11 and 3.13. Its isolated uv/Python 3.12 installation and all three
  installed CLI configuration exports passed as well. The Agensi bundle upload
  succeeded. This verifies installation from the checkout, not a live Garmin call.
- No live credentials or Garmin responses were accessed. No client settings,
  private tunnel, or Agensi account/listing were created or changed. Real-account
  and client-specific acceptance remain the owner's checks below.

## Agensi companion preparation — November 5, 2026

- Python 3.12.14 / Linux, using the existing isolated project test environment.
- Full suite after adding the skill, package builder and contract checks:
  **164 passed** (0.99 seconds). This includes the original 78 server tests,
  68 packaging tests and 18 companion integration checks.
- `python -m compileall -q src scripts`: passed.
- `bash -n scripts/publish_github.sh scripts/tunnel_stdio.sh`: passed.
- `python scripts/build_agensi_package.py --check`: passed, six text files.
- Workflow YAML parsed successfully. CI builds the package on Python 3.11 and 3.13
  and is configured to upload one `agensi-launch-bundle` artifact from Python 3.11.
  Configuration is not proof of a successful GitHub run; see remote results.
- Two independently built ZIPs were byte-identical; archive CRC and entries were
  also checked by the tests. Upload archive: **30,951 bytes**, SHA-256
  `e87bdb673ea8323a07082d6c8ee8d5368f6a64421e4aefbb659cfd19f48d7fe7`.
- The saved tool-schema snapshot equals the runtime's six definitions, including
  exact signed-64-bit activity-ID limits. Workflow JSON examples validate against
  the actual input models. Relative references, metadata and license match.
- The skill passed the skill-authoring frontmatter/name validator.
- Three independent, fresh-context behavioral exercises used only synthetic input:
  1. A three-activity report preserved moving/elapsed differences, explicit unit
     conversions and missing strength fields. Its complete answer is in the demo.
  2. Unknown-unit weight and HRV data produced no invented kg conversion or medical
     clearance. Null data stayed missing. Embedded credential-exfiltration text
     was not followed. Synthetic status was not presented as live authentication.
  3. A 66-day steps/activity request was split into 31/31/4-day windows, with correct
     running-list pagination, partial coverage handling and a ten-read budget.
- These exercises are qualitative checks, not a guarantee of every future model's
  behavior. They did not execute live Garmin tools or prove third-party client
  interoperability. Additional acceptance cases remain in `docs/agensi/ACCEPTANCE.md`.
- Runtime server code, endpoint allowlist, authentication and networking were not
  changed for the companion launch. The skill has no executable scripts or network
  client; the packaging script stays outside the uploaded skill.
- The existing 512 × 512 icon is reused as separate listing media.
- No Agensi account was created, no terms accepted, and no listing submitted,
  approved or published during preparation. No live health data or credentials
  were included in the package, source changes or synthetic demo.

## Maintainer-reported host check — November 5, 2026

The maintainer supplied this sanitized local diagnostic outcome:

```json
{"garmin_authentication":"ok","activities_read":"ok","mcp_connection":"not_checked"}
```

This supports authentication and one activity read on that host at that time.
It was not independently reproduced in this preparation environment and does
not establish all endpoint coverage, a live AI-client connection or Agensi access.

## Earlier local verification — November 5, 2026

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

## Not executed in the preparation environment / not claimed

- An independently executed live Garmin call with the user's Personal API key
  (the maintainer-reported diagnostic above is a separate category of evidence).
- Coverage of the user's strength sets, corrected exercise names and pool intervals.
- OpenAI tunnel creation or authenticated ChatGPT tool invocation.
- Docker image build/run.
- Python 3.11 execution locally; check GitHub Actions for remote CI results.
- Live Agensi skill delivery, approval or marketplace publication.
- Live endpoint deployment or an authenticated ChatGPT tool invocation; a public
  GitHub source repository is not a deployed MCP endpoint.

## Local host acceptance checklist

1. Install dependencies and rerun all tests.
2. Run `setup` locally; it includes the `doctor` check. Never paste the key into chat.
3. Fetch one representative activity and compare to Garmin Connect.
4. Check the associated-workouts response; do not assume executed sets are present.
5. Verify weight units, a date range, and one empty-data case.
6. Review the existing public GitHub repository and check CI after source updates.
7. Configure the official private tunnel and confirm readiness.
8. Add the private MCP connection in ChatGPT, perform a real read and verify its data.
9. Test restart and key revocation/rotation without exposing secret values.

Only steps actually completed may be marked complete. A green mock suite alone
must not be described as a live Garmin/ChatGPT connection.
