# Setup, client settings, and recovery

Start with the [three-step quick start](../README.md#quick-start-linuxmacos).
The normal connection needs **one Garmin Personal API key**, not a manually
generated access token, HTTP bearer, OpenAI key, or Garmin password.

## Local client settings

Run `garmin-connect-mcp client-config` on the machine that runs your AI client.
It only prints configuration: it does not read secret-file contents, contact
Garmin, register a server, or change your other client settings.

| Client | Output command | Where it belongs |
|---|---|---|
| Claude Code | `garmin-connect-mcp client-config` | Local MCP configuration; the JSON uses `mcpServers`. For `claude mcp add-json`, pass only the inner `garmin` object, not the wrapper. |
| Cursor | `garmin-connect-mcp client-config` | Merge into `~/.cursor/mcp.json` for your user. |
| VS Code | `garmin-connect-mcp client-config --format vscode` | User-profile `mcp.json`, opened with **MCP: Open User Configuration**; this format uses `servers`. |
| Codex | `garmin-connect-mcp client-config --format codex` | Merge the `mcp_servers.garmin` tables into `~/.codex/config.toml`. |

Keep existing entries. If `garmin` already exists, review and update that entry
instead of adding a duplicate. Prefer user-local settings for personal health
tools; do not commit your generated machine-specific configuration. Approve/enable
the server in the client and perform one actual read before calling it connected.
These formats follow official documentation; they are not claims of live
interoperability with every client/version.

The generated command uses the Python interpreter from the connector's actual
installation, so virtual environments and paths containing spaces work without
shell quoting. The configuration includes an absolute key-file path and the
selected timezone, but no key or HTTP token. It is not portable to another host,
container, or cloud agent. Regenerate it if the installation/key path changes.

For a browser-based ChatGPT connection, use [the private tunnel guide](CHATGPT.md)
instead. GitHub hosts code, not a running endpoint. The computer hosting the
connector must remain available during reads.

## Installation and updates

The recommended uv command in the README installs directly from this repository
into an isolated environment and requests Python 3.12. It requires uv, Git, and
HTTPS access to the source and dependency hosts; uv may download its managed Python.
Do not replace Ubuntu's system Python just for this connector. No development
dependencies or test execution are required for ordinary use.

For an existing uv installation:

```bash
uv tool upgrade garmin-connect-mcp
garmin-connect-mcp setup
```

If you prefer an editable clone and already have **Python 3.11 or newer**:

```bash
git clone https://github.com/graiola/garmin-connect-mcp.git
cd garmin-connect-mcp
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/garmin-connect-mcp setup
```

Check `python3 --version` first; on a Python-3.10-only machine use the uv route or
an explicitly installed supported interpreter. The commands above need no venv
activation. Use `.venv/bin/garmin-connect-mcp client-config` for that installation.

To update an existing clone, from its root:

```bash
git pull --ff-only
.venv/bin/python -m pip install -e .
.venv/bin/garmin-connect-mcp setup
```

Stop if Git reports conflicting/local changes; preserve them. Do not configure a
second installation accidentally. Reuse your existing key, regenerate the client
configuration if its executable path changed, and restart the MCP process through
your client. Documented setup targets Linux/macOS; Windows acceptance is unverified.

## What setup checks and stores

`setup` uses the effective configured key, or prompts once with hidden input when
none is configured. It performs the same read-only probe as `doctor`: authenticate
with Garmin and request one activity. No activity records or credentials are
printed. A newly entered key is saved only after a successful probe, at
`~/.config/garmin-connect-mcp/api-key`, outside the repository. POSIX file
permissions are `0600`. Running setup again does not overwrite a working key.

Success messages go to stderr; the printed client configuration goes to stdout.
`doctor` retains its JSON diagnostic with `mcp_connection: not_checked`. Neither
command proves agent connectivity or the accuracy/availability of every metric.

Garmin's temporary access tokens stay in memory and are renewed automatically.
They cannot renew an expired/revoked Personal API key. Generate a new key in
Garmin Connect and run `garmin-connect-mcp setup --replace-key` in your own terminal.
The candidate is checked before an atomic replacement of the managed default
file. A failed probe preserves the old file. Restart any running connector after
rotation; changing a file does not update an already-running process.

Never paste a key into chat or command arguments. `setup` refuses secret entry
without hidden interactive input. Do not run its credential prompt in an
AI-operated terminal, recorded session, or a pipe. Ctrl-C cancels setup.

## Environment and secret-manager options

Garmin key precedence is explicit file → environment value → default file:

1. `GARMIN_PERSONAL_API_KEY_FILE`: an absolute private file path is recommended.
2. `GARMIN_PERSONAL_API_KEY`: supplied by your secret manager, never typed literally
   into command arguments, committed configuration, or chat.
3. `~/.config/garmin-connect-mcp/api-key`: the normal setup-managed file.

A configured but invalid/missing source is an error, not a reason to try another
account/key. `.env` files are **not** loaded automatically. Secret files must be
small, private regular files. Fix permissions yourself locally when instructed;
do not share the contents for debugging.

Setup reuses overrides without copying or changing them. For environment-only
credentials it can check Garmin, but will not print a client configuration that
embeds the key or silently selects a different default file. Either arrange that
the client process receives the variable through its supported secret mechanism,
or remove the override in your own terminal and run setup to enter a key into the
managed file. GUI applications do not necessarily inherit terminal variables.
`setup --replace-key` refuses overrides; rotate those in your secret manager.

Set `GARMIN_MCP_TIMEZONE` before setup/config generation, for example
`export GARMIN_MCP_TIMEZONE=Europe/Rome`. Use your own IANA timezone; the default
is Europe/Rome. This controls local date reporting, not upstream timestamp
conversion. Regenerate the client configuration after changing it.

## Optional local HTTP

Skip this section for local stdio clients and the stdio ChatGPT tunnel.
To prepare an independent bearer token and start the loopback HTTP transport:

```bash
garmin-connect-mcp configure-http
garmin-connect-mcp http --port 8765
```

`configure-http` creates `~/.config/garmin-connect-mcp/http-token` only when no
HTTP credential is configured; it reuses an existing one and never prints its
value. Alternative secret-manager variables are `GARMIN_MCP_ACCESS_TOKEN_FILE`
and `GARMIN_MCP_ACCESS_TOKEN`. The file wins. The bearer must be at least 32
characters and different from the Garmin key.

HTTP serves `/mcp` on **127.0.0.1 only**, with Host/Origin checks and bearer
authentication. Supply the bearer through your HTTP client's secret mechanism;
do not put it in a URL or chat. `/healthz` checks the process, not Garmin access.
This server does not implement OAuth. Do not expose it publicly to simplify setup.
Stdio, setup, and doctor do not require or load HTTP credentials.

The older `configure` command remains available for offline/manual setup. It
creates the default key and legacy HTTP token without a Garmin probe, refuses
existing keys/overrides, and must be followed by `doctor`. Prefer `setup` normally.

## Development only

In a supported Python virtual environment, from the repository root:

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m compileall -q src scripts
bash -n scripts/publish_github.sh scripts/tunnel_stdio.sh
```

`requirements-tested.txt` records the original tested versions, not a portable
lockfile. Tests use synthetic credentials and data; see [VERIFICATION.md](VERIFICATION.md).

## Official references

Checked November 6, 2026:

- [Garmin key creation and expiry](https://developer.garmin.com/gc-developer-program/personal/personal-faq/)
- [uv tool installation and upgrades](https://docs.astral.sh/uv/guides/tools/)
- [uv Python management](https://docs.astral.sh/uv/guides/install-python/)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [Cursor MCP](https://cursor.com/docs/mcp)
- [VS Code MCP configuration](https://code.visualstudio.com/docs/agents/reference/mcp-configuration)
- [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp)
