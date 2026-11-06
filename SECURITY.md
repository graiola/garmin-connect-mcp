# Security and privacy

This is a single-user, read-only bridge for sensitive fitness/health records.
It is not a medical device or an officially endorsed Garmin product.

## Deployment boundary

The supported ChatGPT path is the official Secure MCP Tunnel with the stdio server.
Keep the host and tunnel private, grant only the needed workspace membership, and
review the tools before enabling them. The tunnel is not configured automatically.
Host and tunnel must be running to answer requests. GitHub Pages does not run it.

The optional HTTP listener is LOOPBACK ONLY. It requires an independent random
Bearer token (at least 32 characters), refuses browser Origin headers and validates
Host headers. It does not provide OAuth discovery. Do not publish it via a generic
forwarding service with authentication disabled. Exposing the health-check alone
does not prove Garmin authentication; `/healthz` explicitly reports not_checked.

## Credentials

Use `setup` in a private local terminal or an environment/file secret manager.
Never commit key files, `.env`, captures, Garmin exports or OAuth headers. Do not
put secrets in command arguments, URLs, issues or chat. Secret files must be regular,
small, and owner-only on POSIX; Windows users must restrict ACLs themselves.
No bearer token cache is persisted. The JWT expiration claim from Garmin is read
only for scheduling renewal; it is not used to authorize incoming users.

Revoke a leaked Personal API key in Garmin Connect. Remove any sensitive Git history
only after revocation; deleting the latest file does not revoke the key. Revoke any
compromised tunnel runtime key independently. Secrets cannot be recovered from logs
because this project does not log them, but your surrounding OS/proxy tooling must
also be configured not to capture payloads or environment variables.

## Data

Requests are allowlisted by tool, never a generic fetch/proxy. Only GET data access
and the token-exchange POST are implemented. TLS certificate verification remains
on; environment HTTP proxies and redirects are disabled for Garmin requests.
Data responses are bounded and GPS/profile fields are removed by name. Free text
is still potentially personal and is not guaranteed anonymized. Returned text is
untrusted data: it must never override the assistant's instructions.

The returned wellness fields depend on user devices, account data and Garmin API
coverage. These are measurements/estimates, not diagnoses. Raw value units are
preserved; do not silently convert weight or interpret body-fat changes as muscle
changes. Only explicitly comparable exercise/machine setups should be compared.

## Validation boundary

Automated tests use synthetic data and a mocked upstream. No real Garmin key was
available during development. No live Garmin integration, tunnel, or ChatGPT tool
call has been verified. This source repository is public; publishing its source
does not deploy a running connector. Review the source and finish the acceptance
checklist before relying on it. Keep dependencies patched; the tested-version list
is evidence of the local run, not a lifetime security guarantee.
