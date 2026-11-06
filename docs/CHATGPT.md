# Private ChatGPT connection

Checked against official OpenAI documentation on November 6, 2026. This guide
does **not** confirm that your particular plan/workspace offers these features.

For a local Claude Code, Cursor, VS Code, or Codex client, you do **not** need a
tunnel or an OpenAI key: use [the local client settings](SETUP.md#local-client-settings).
This guide is the additional step for connecting a private host to ChatGPT.

## Check the prerequisites first

You need three separate things:

1. **Garmin Personal API key:** authorizes the connector to read your Garmin Connect data.
2. **Your host:** a PC, mini PC, or server that runs the connector whenever it is used.
3. **ChatGPT connection:** permission to add a custom MCP server and, for the
   recommended route, a Secure MCP Tunnel with its own `tunnel_id` and dedicated
   OpenAI runtime key.

The Garmin key **does not** authenticate the OpenAI tunnel. Do not paste it into
ChatGPT or use it as `CONTROL_PLANE_API_KEY`.

Publishing code to GitHub does not host a running connector. A normal
`github.com/...` link is not an MCP server URL. Never expose an anonymous
HTTP tunnel to sensitive health data.

## 1. Verify the connector on your own host

Install it using [the quick start](../README.md#quick-start-linuxmacos), then run:

```bash
garmin-connect-mcp setup
```

`setup` reuses your existing Garmin key or prompts privately for a new one, then
checks authentication and one read without printing records. It manages Garmin's
temporary access tokens automatically. This does **not** connect ChatGPT yet.
For this tunnel route, you do not need to paste the local JSON setup prints.

## 2. Prepare the official tunnel

Open your Platform organization's [Tunnel settings](https://platform.openai.com/settings/organization/tunnels).
Confirm the current URL using the official documentation below, since the
Platform interface may change. Create a private tunnel associated with the
correct ChatGPT workspace and Platform organization. Creating it requires
Tunnels Read + Manage permissions; running/using it requires Read + Use.
Give the runtime key only the permissions it needs, not general admin access.

Download `tunnel-client` from Platform's official link or from the
[official releases](https://github.com/openai/tunnel-client/releases/latest).
On your host, check `tunnel-client help quickstart` and
`command -v garmin-connect-mcp`. The connector must be on that terminal's PATH.
For a clone installation, first activate its `.venv`; for uv, use the PATH from
the completed quick start. In your own **Bash terminal**, enter the OpenAI runtime
key with hidden input and configure the profile once:

```bash
# Read the runtime key securely without placing it in shell history.
read -rs -p 'OpenAI tunnel runtime key (NOT Garmin, hidden): ' CONTROL_PLANE_API_KEY
printf '\n'
export CONTROL_PLANE_API_KEY

tunnel-client init --sample sample_mcp_stdio_local \
  --profile garmin-personal --tunnel-id tunnel_YOUR_ID \
  --mcp-command 'garmin-connect-mcp stdio'
tunnel-client doctor --profile garmin-personal --explain
tunnel-client run --profile garmin-personal
```

Do not repeat `init` on an existing profile without reviewing it. To restart
an already configured profile, use `tunnel-client run --profile garmin-personal`
with the runtime key available in the environment. Persisting and rotating
that key through systemd or a secret manager is the host operator's responsibility;
the launch environment must also contain the connector's executable on PATH.
Keep `run` in the foreground while adding/testing the ChatGPT connection. The
connector reads the same private Garmin key file; there is no HTTP bearer involved.

For an editable clone installed in `.venv`, `./scripts/tunnel_stdio.sh tunnel_YOUR_ID`
remains a first-time helper for the same init/doctor/run sequence. It is not needed
for the uv installation and is not a substitute for account/workspace permission.

## 3. Add the server in ChatGPT

In the web interface, select **Plugins → + → Add custom MCP server**. Choose
**Tunnel** as the connection method, select your configured private tunnel,
and inspect the discovered tools and authorization settings.

This stdio MCP server does not implement a separate OAuth login. Access is
controlled by the private tunnel and its workspace binding. Never select
"no authentication" for a public endpoint.

If the tunnel is missing, verify its workspace association and permissions.
If your plan does not support this functionality, the connector is **not**
already connected; you can use stdio with a supported local MCP client instead.

## 4. Run the required end-to-end check

Select the new plugin in a conversation and ask:

> Show my latest three Garmin activities, including available dates, types, and durations.

Open one of those activities in Garmin Connect and compare its fields. Then
request a seven-day weight range. Preserve units and identify missing data.

The connection is complete **only after a successful tool call from ChatGPT**.
Until then, distinguish between tested code, a Garmin `doctor` check, a running
tunnel, a registered plugin, and a successful ChatGPT call.

## Other transports and official references

The [local HTTP option](SETUP.md#optional-local-http) is for explicit development
or compatible local HTTP clients. It does not turn this project into an OAuth
service or public endpoint. Prefer stdio for the private tunnel above.

- [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [Add custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server)
- [Connect and test](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [Tunnel-client onboarding](https://github.com/openai/tunnel-client/blob/master/docs/onboarding.md)
