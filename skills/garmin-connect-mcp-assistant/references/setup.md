# Connection and local setup

Prerequisite: the user's own Garmin account with Personal API access, their own
configured instance of [graiola/garmin-connect-mcp](https://github.com/graiola/garmin-connect-mcp),
and an agent able to call its tools. Version `0.1.0` requires Python 3.11 or newer.
This guide documents Linux/macOS; do not claim Windows acceptance without testing.

Agensi delivers the skill through its own connection. It does not supply a Garmin
account, install the server, host it, or configure the user's agent. The agent must
also have access to the Garmin MCP connection. A GitHub URL is source code, not a
running MCP endpoint. Do not promise compatibility with all clients.

## User-run installation

Offer these commands only when setup is requested. Obtain permission before making
changes on the user's machine. Keep secret entry out of an AI-operated terminal
or tool transcript; `configure` is for the user's own interactive terminal.

```bash
git clone https://github.com/graiola/garmin-connect-mcp.git
cd garmin-connect-mcp
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
garmin-connect-mcp configure
garmin-connect-mcp doctor
```

Verify that the chosen Python is at least 3.11 before creating the environment.
If it is older, direct the user to install a supported Python using their OS's
documented process; do not blindly suggest system-wide package or interpreter
changes. This project is installed from its verified repository, not an assumed
same-name package registry entry.

`configure` prompts without echo and stores protected files outside the repository.
It refuses to overwrite an existing key file. Do not read, print, collect, copy,
delete or change those files on the user's behalf just to diagnose a connection.
If rotation is needed, explain that the user must perform it locally and keep
permissions restricted. Never use a Garmin password, cookie or scraping fallback.

`doctor` performs one real activity read and prints a diagnostic outcome, not
activity records. A successful result still says `mcp_connection: not_checked`.
It is not proof that the user's agent, Agensi or every metric works.

## Agent connection

For a local stdio-capable client, configure the actual absolute executable path:

```text
/absolute/path/to/garmin-connect-mcp/.venv/bin/garmin-connect-mcp stdio
```

Client configuration formats differ. Use the client's current official setup
instructions instead of inventing settings. Store credentials on the host, not in
the skill, marketplace listing or chat. The host must remain available during reads.

The connector can also expose authenticated Streamable HTTP on `127.0.0.1` only.
It requires a separate MCP bearer token, not the Garmin key, and is not an OAuth
server. Do not weaken its bind address, Host/Origin checks or token protection to
make a marketplace connection work. For remote clients, use a supported private,
authenticated connection method; its availability must be checked for that client.
Refer to the repository's [connection guide](https://github.com/graiola/garmin-connect-mcp/blob/master/docs/CHATGPT.md)
for its documented private-tunnel option; do not claim this has been tested in the
current account.

Optional timezone setting: configure `GARMIN_MCP_TIMEZONE` on the connector host
to the user's IANA timezone, such as `Europe/Rome`, and restart the process if
needed. This controls local date reporting, not upstream Garmin timestamp conversion.

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
