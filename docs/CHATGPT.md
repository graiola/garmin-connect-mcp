# Private ChatGPT connection

Checked against official OpenAI documentation on November 5, 2026. This guide
does **not** confirm that your particular plan/workspace offers these features.

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

Install it as described in the README, then run:

```bash
source .venv/bin/activate
garmin-connect-mcp configure
garmin-connect-mcp doctor
```

`configure` prompts for the Garmin key using hidden input. `doctor` performs
a real read and reports only success/failure. This does **not** connect ChatGPT
yet. Your key file stays outside the repository.

## 2. Prepare the official tunnel

Open your Platform organization's [Tunnel settings](https://platform.openai.com/settings/organization/tunnels).
Confirm the current URL using the official documentation below, since the
Platform interface may change. Create a private tunnel associated with the
correct ChatGPT workspace and Platform organization. Creating it requires
Tunnels Read + Manage permissions; running/using it requires Read + Use.
Give the runtime key only the permissions it needs, not general admin access.

Download `tunnel-client` from Platform's official link or from the
[official releases](https://github.com/openai/tunnel-client/releases/latest).
On your host, check `tunnel-client help quickstart`. After creating the tunnel:

```bash
./scripts/tunnel_stdio.sh tunnel_YOUR_ID
```

The script configures a `garmin-personal` profile, checks it with `doctor`,
and stays in the foreground with `run`. The OpenAI key is entered locally
without echoing and is neither printed nor persisted by the script. The
connector inherits Garmin-related environment variables or reads the external
file created by `configure`.

Equivalent manual setup:

```bash
# Read the runtime key securely without placing it in shell history.
read -rs -p 'OpenAI tunnel runtime key: ' CONTROL_PLANE_API_KEY; echo
export CONTROL_PLANE_API_KEY

tunnel-client init --sample sample_mcp_stdio_local \
  --profile garmin-personal --tunnel-id tunnel_YOUR_ID \
  --mcp-command '/path/to/garmin-connect-mcp/.venv/bin/garmin-connect-mcp stdio'
tunnel-client doctor --profile garmin-personal --explain
tunnel-client run --profile garmin-personal
```

Do not repeat `init` on an existing profile without reviewing it. To restart
an already configured profile, use `tunnel-client run --profile garmin-personal`
with the runtime key available in the environment. Persisting and rotating
that key through systemd or a secret manager is the host operator's responsibility.

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

## Official references

- https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
- https://developers.openai.com/plugins/deploy/connect-chatgpt
- https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
- https://github.com/openai/tunnel-client/blob/master/docs/onboarding.md

## Local HTTP mode (development alternative)

`garmin-connect-mcp http` serves `/mcp` at `127.0.0.1:8765`, with a separate
bearer token, Host validation, browser Origin rejection, and stateless JSON
responses. It does not offer OAuth or a public endpoint. `/healthz` checks
only the process, not Garmin authentication.

A local MCP HTTP client may send the Authorization header using the `http-token`
file via a secret manager. Do not paste that token into a URL or chat. For the
ChatGPT tunnel, the stdio option above avoids additional HTTP configuration
and remains the recommended route.
