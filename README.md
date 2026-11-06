<p align="center">
  <img src="assets/icon.png" alt="Garmin Connect MCP icon: fitness watch with a connected pulse" width="160">
</p>

<h1 align="center">Garmin Connect MCP</h1>

A personal, **read-only** MCP connector for the official Garmin Connect Personal API,
supporting MCP over stdio and local Streamable HTTP. Built to help explore workouts
and fitness trends—not to diagnose medical conditions.

**Free, MIT-licensed, and self-hosted.** You supply one Garmin Personal API key;
the connector manages Garmin's temporary access tokens automatically. Never paste
your key into chat, an agent configuration, or the repository.

## Quick start (Linux/macOS)

### 1. Create your Garmin key

In [Garmin Connect Web](https://connect.garmin.com/), open **Profile & Account →
Account Settings → Personal API Key → Create Key**. Review Garmin's terms, choose
an expiry, and keep the key private: Garmin displays it only once.
See the [official instructions](https://developer.garmin.com/gc-developer-program/personal/personal-api/).
Already have a working key on this machine? Reuse it; no need to create another.

### 2. Install and run guided setup

With [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git installed,
run these commands in **your own terminal**:

```bash
uv tool install --python 3.12 git+https://github.com/graiola/garmin-connect-mcp.git
garmin-connect-mcp setup
```

uv manages the isolated environment and downloads Python 3.12 if needed; you do
not need to change your system Python or activate a virtual environment. If the
command is not found, follow uv's PATH instructions (`uv tool update-shell`, then
open a new terminal). This installs from this repository, not a same-name PyPI entry.

`setup` asks for the key with hidden input, checks Garmin authentication and one
activity read, then saves a valid new key outside the repository with restricted
permissions. It reuses an existing configured key when run again. It prints no
key or activity records and creates no HTTP token for the normal local connection.

Already installed from a clone, or prefer plain Python? See
[installation and updates](docs/SETUP.md#installation-and-updates).

### 3. Connect your local AI client

Setup prints a configuration containing the actual Python path and a **path to**
the key file, never the key. Merge its `garmin` entry into your client's local MCP
settings, preserving existing servers. To print it again or choose another format:

| Client/configuration | Command |
|---|---|
| Claude Code / Cursor (`mcpServers` JSON) | `garmin-connect-mcp client-config` |
| VS Code (`servers` JSON) | `garmin-connect-mcp client-config --format vscode` |
| Codex (`config.toml`) | `garmin-connect-mcp client-config --format codex` |

Follow the [client-specific locations](docs/SETUP.md#local-client-settings), approve
the server in your client, then ask: **"Show my three latest Garmin activities."**
Compare one result with Garmin Connect. The local client starts the server for
you; no separate `stdio` terminal or public port is needed. The configuration
belongs on the same machine as the connector and key.

**Using ChatGPT in a browser instead?** A local JSON configuration is not enough.
Follow the separate [private ChatGPT connection guide](docs/CHATGPT.md). That route
requires a supported account/workspace and an OpenAI Secure MCP Tunnel; its
runtime key is separate from the Garmin key.

Setup verifies Garmin access, **not** the AI-client connection. Installing the
companion skill from Agensi does not perform either connection step.

## Available tools

| Tool | Data returned |
|---|---|
| `garmin_list_activities` | Paginated activities, optionally filtered by date and type |
| `garmin_get_activity` | Raw activity summary and details |
| `garmin_get_activity_workouts` | Associated workouts, containing only fields actually returned by Garmin |
| `garmin_get_health_range` | Weight, steps, stress, sleep, HRV, Body Battery, and daily summaries |
| `garmin_get_day_detail` | Sleep, HRV, or heart-rate details for a day |
| `garmin_connector_status` | Capabilities, local date, and version; does **not** validate credentials |

Dates are explicit (`YYYY-MM-DD`), with `Europe/Rome` as the default time zone.
Health ranges are capped at 31 inclusive days, and activities at 50 per page.
There are no Garmin write operations, deletions, workout planning, or uploads.

**Strength-training limitation:** Garmin's official `workouts` endpoint does not
guarantee actual performed sets, edited exercise names, weights, or reps. This
connector does not decode FIT files or fabricate missing data. Compare one of your
own strength sessions against Garmin Connect before relying on it instead of a
detailed export. Loads on different machines are not automatically comparable.

## Key renewal and troubleshooting

Temporary Garmin access tokens are renewed automatically while your Personal API
key is valid. When that key expires or is revoked, create a replacement in Garmin
Connect and run this in your own terminal:

```bash
garmin-connect-mcp setup --replace-key
```

A failed check does not replace the previous key. Restart the connector through
your client after a successful replacement. To check the current key without
changing it, run `garmin-connect-mcp doctor`.

See [setup and troubleshooting](docs/SETUP.md) for environment/secret-manager
overrides, timezones, optional HTTP, and developer installation.

## Repository and security

The GitHub repository is currently **public**. Do not push any Garmin key,
OpenAI token, personal health data, FIT export, or captured response. The
`scripts/publish_github.sh` helper only bootstraps a **new** private repository
and intentionally refuses to overwrite an existing one; it is not used for
updates to this repository.

- Only allowlisted official Garmin endpoints are called; no scraping, password
  login, reverse-engineered sessions, cookies, or arbitrary URLs.
- Keys are exchanged for short-lived tokens when needed; tokens remain in memory.
  A `401` triggers at most one fresh exchange and retry.
- Requests have bounded timeouts, concurrency, retries, and response sizes.
- GPS coordinates and selected identifiers are filtered recursively. **This is
  not full anonymization:** activity names and free-form notes can contain
  personal information.
- The connector does not independently send data to an LLM. When you call its
  tools from ChatGPT, responses pass through the connected services and chat.
- Errors are sanitized; authorization headers and response bodies are not logged.
- The lightweight, tools-only MCP transport does not implement persistent SSE,
  OAuth, resources, prompts, or experimental tasks.
- Requests run on demand; there is no background monitoring or scraping.

Read [SECURITY.md](SECURITY.md), the [API contract](docs/API_CONTRACT.md), and
the [verification record](docs/VERIFICATION.md). This is a single-user personal
connector, not a multiuser or public health-data service.

## Free companion skill and Agensi preparation

[Garmin Connect MCP Assistant](skills/garmin-connect-mcp-assistant/SKILL.md) teaches
an agent to use these six tools with bounded reads, explicit dates, missing-data
handling and privacy safeguards. It is MIT-licensed and does not change the server.
It does not include credentials, host a connector, install one automatically, or
provide medical diagnoses or guaranteed performed strength sets.

The skill source is available now. An Agensi listing is **prepared, not submitted
or approved**. Users loading it there will still need their own configured Garmin
MCP connection in the same agent. Compatibility with specific third-party clients
must be verified by a real read; local mocked tests are not sufficient.

Build the exact six-file, text-only upload package with Python 3.11+:

```bash
python scripts/build_agensi_package.py --check
python scripts/build_agensi_package.py
```

The ZIP and SHA-256 checksum are written under `dist/agensi/`. After successful
CI, the `agensi-launch-bundle` Actions artifact also contains the upload ZIP,
existing 512 × 512 logo and prepared listing materials. Extract that outer artifact
before uploading the inner skill ZIP; do not upload the whole repository.

See the [launch guide](docs/agensi/LAUNCH.md),
[listing description](docs/agensi/LISTING.md),
[synthetic demonstration](docs/agensi/DEMO.md), and
[acceptance checklist](docs/agensi/ACCEPTANCE.md).

## Acceptance prompts after connecting

1. "Show my three latest activities without making fitness conclusions."
2. "Open activity X and show only measurements that are actually available."
3. "Compare two swims, separating moving time, elapsed time, and rest."
4. "Read my last 14 days of weigh-ins, preserve original units, and flag gaps."

Verify at least one activity against Garmin Connect. Passing local mocked tests
does **not** prove real data accuracy or compatibility with your ChatGPT account.

**Verification status:** the maintainer reported a successful local `doctor` on
November 5, 2026 (authentication and one activity read). This was not independently
repeated here. The version 0.2.0 onboarding has synthetic regression tests; live
AI-client, Secure MCP Tunnel, and Agensi acceptance remain separate checks.
