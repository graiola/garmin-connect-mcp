# Connection and local setup

Contents: [Setup and recovery](#keep-the-normal-path-short) ·
[Client connection](#agent-connection) · [Acceptance](#acceptance-sequence)

Use the user's own [Garmin Connect MCP](https://github.com/graiola/garmin-connect-mcp)
instance, version `0.2.0` or newer, on a host they control. Python 3.11+ is required;
the recommended uv installation manages Python 3.12. Setup documents Linux/macOS,
not verified Windows acceptance.

Agensi delivers the skill through its own connection. It does not supply a Garmin
account, install the server, host it, or configure the user's agent. The agent must
also have access to the Garmin MCP connection. A GitHub URL is source code, not a
running MCP endpoint. Do not promise compatibility with all clients.

## Keep the normal path short

Offer setup only when requested. Obtain permission before installing anything.
Have the user enter secrets in their own private terminal, never an AI-operated
terminal, tool transcript, command argument, or chat. Do not read key files or
environment secret values for troubleshooting.

Have the user create a **Personal API key** in Garmin Connect Web: Profile &
Account → Account Settings → Personal API Key. They review the terms and select
an expiry themselves. Reuse an already configured key. See
[Garmin's instructions](https://developer.garmin.com/gc-developer-program/personal/personal-api/).
With [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git available,
offer these commands in the user's own terminal:

```bash
uv tool install --python 3.12 git+https://github.com/graiola/garmin-connect-mcp.git
garmin-connect-mcp setup
```

uv can download the requested Python without replacing system Python. If the
executable is not found, follow uv's PATH guidance (`uv tool update-shell`, then a
new terminal). Install from this verified repository, not an assumed same-name
PyPI package. Existing clone users should update their installation using the
[setup guide](https://github.com/graiola/garmin-connect-mcp/blob/master/docs/SETUP.md#installation-and-updates).

`setup` reuses the effective key or prompts with hidden input, checks authentication
and one activity read, then saves a valid new key privately outside the repo. It
prints no measurements and creates no HTTP token. The connector obtains/renews
temporary Garmin access tokens automatically; users do not generate or paste them.
This does not renew an expired Personal API key.

For an expired/revoked key, have the user create a replacement in Garmin Connect
and run `garmin-connect-mcp setup --replace-key` themselves. A failed probe leaves
the previous managed file unchanged. Restart the connector after replacement.
Never inspect, copy, delete or change credentials on the user's behalf, or use a
password, cookie, alternate account, or scraping fallback.

Explicit key-file/environment overrides take precedence over the managed file.
Setup reuses them, and replacement refuses to modify them. Environment-only keys
are not silently persisted or embedded in generated configuration; GUI clients may
not inherit them. Refer to the setup guide's secret-manager instructions instead
of suggesting a literal key in JSON or shell history.

`doctor` checks the current key without modifying it and still reports
`mcp_connection: not_checked`. Neither setup nor doctor verifies the user's AI
client, Agensi, every endpoint, or data accuracy.

## Agent connection

For a local stdio client, merge the printed `garmin` entry into its local MCP
settings, preserving other servers. Print the right format as needed:

| Configuration | Command |
|---|---|
| Claude Code / Cursor (`mcpServers` JSON) | `garmin-connect-mcp client-config` |
| VS Code (`servers` JSON) | `garmin-connect-mcp client-config --format vscode` |
| Codex TOML | `garmin-connect-mcp client-config --format codex` |

Use [documented client locations](https://github.com/graiola/garmin-connect-mcp/blob/master/docs/SETUP.md#local-client-settings),
not invented universal settings. The helper prints actual executable/key-file
paths, not secrets, and changes no client settings. The configuration is for that
host, not a cloud agent. The host must remain available during reads.

For browser-based ChatGPT, follow the [private tunnel guide](https://github.com/graiola/garmin-connect-mcp/blob/master/docs/CHATGPT.md).
It needs supported account/workspace access and a separate OpenAI runtime key.
Do not request that key in chat or substitute the Garmin key. A local JSON file
or GitHub URL does not connect a browser client.

Local HTTP is optional: `configure-http` prepares a separate bearer for loopback-only
`http`. Neither stdio nor its private tunnel needs it. Never weaken networking or
authentication, or promise an OAuth server, to simplify onboarding.

Set `GARMIN_MCP_TIMEZONE` to the user's IANA timezone before generating settings.
Regenerate settings if it changes. Europe/Rome is a default, not proof of location;
this controls local date reporting, not upstream Garmin timestamp conversion.

## Acceptance sequence

1. Discover the six tools through the actual client.
2. Call status; confirm version, read-only mode, local date and timezone. Do not
   mistake `garmin_authenticated: not_checked` for a failure or success.
3. At the user's request, read one activity and compare its values with Garmin
   Connect. Keep the values private; record only whether the check passed.
4. Check a requested metric/date and a missing-data case. One activity read does
   not verify all metric endpoints.
5. If using Agensi, load the skill there and repeat a minimal actual Garmin read
   from the same agent. Only then claim that end-to-end combination was verified.

Garmin's Personal API is for individual access to one's own data, not a hosted
commercial service for multiple users. Each person uses their own key. Any future
paid or hosted offering needs a separate review of the applicable Garmin terms.
Official reference: https://developer.garmin.com/gc-developer-program/personal/personal-faq/
