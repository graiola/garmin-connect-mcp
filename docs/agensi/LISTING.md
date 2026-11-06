# Garmin Connect MCP Assistant

Free, open-source instructions that help your AI agent explore your own Garmin
activities and available wellness data through Gennaro Raiola's read-only
[Garmin Connect MCP](https://github.com/graiola/garmin-connect-mcp).

**Requires your own configured Garmin MCP server, connected to the same agent.**

The server's guided `setup` checks your key and prints local client settings.
Garmin's temporary access tokens are managed automatically. Your key is entered
only in your own terminal; installing this skill does not connect the server for you.
This listing supplies the companion skill, not server hosting, installation,
Garmin credentials or an account connection.

## What it helps you do

- Summarize recent activities with the measurements Garmin actually returns.
- Compare sessions while keeping moving time, elapsed time and rest distinct.
- Review steps, weight, stress, sleep, HRV, Body Battery and daily summaries where
  available from your account and device.
- Inspect an activity's associated workout without inventing missing strength sets.
- Query explicit dates, page through relevant activities, and split longer health
  requests into bounded date windows.
- Understand missing data, raw units, partial coverage and connection errors.

## Example requests

- "Show my three latest activities. Tell me which measurements are missing."
- "Compare these two swims, separating moving pace from rest-inclusive pace."
- "Summarize my steps for last week and show how many days have data."
- "Check whether my strength session includes performed sets and weights."
- "Explain what a successful connector status check does and does not prove."

## How it works

Your agent loads these instructions through Agensi, then calls the separately
connected Garmin MCP tools as needed. The skill contains only text instructions,
references and a tool-schema snapshot. It does not run a server or make network
requests itself. The connector uses the official Garmin Connect Personal API;
the project is independent and is not endorsed by Garmin or Agensi.

## What you need

1. Your own Garmin account and Garmin Personal API access.
2. A configured instance of `graiola/garmin-connect-mcp`, running on your own host.
3. An AI agent that can call that connector and can load the skill from Agensi.

The connector requires Python 3.11 or newer. Its documented setup targets
Linux/macOS, with stdio for local clients and authenticated loopback HTTP as an
alternative. Remote access needs a supported private, authenticated connection.
This is not a promise of compatibility with every agent; confirm your chosen
client with a real read before relying on the workflow.

## Clear limitations

- Read-only: no activity editing, deletion, workout uploads or account changes.
- No FIT downloads or decoding. Associated workouts do not guarantee actual
  performed sets, edited exercise names, repetitions or weights.
- No dedicated training-readiness, VO2 max or fitness-age tool.
- Availability and raw response shapes depend on Garmin, the account and device.
- Wearable scores and body-composition measurements are estimates, not medical
  diagnoses or clearance to train. This is a data assistant, not medical care.
- No background monitoring. Reads happen on demand within the requested scope.

## Privacy

Enter your Garmin key only in your own local terminal; never paste it into chat
or the marketplace. The connector filters selected structured location and
identity fields, but activity titles and notes may still identify you. Returned
data is processed by your connected AI provider; it is not guaranteed to stay on
your device. The skill tells the agent not to send Garmin records or credentials
to marketplace search, feedback or submission tools.

## Free and open source

The server and this companion skill are available under the MIT license in the
[source repository](https://github.com/graiola/garmin-connect-mcp). Garmin's own
Personal API terms still apply to each user's account. This is not a hosted
multi-user Garmin service, and no commercial API entitlement is included.

Start with the [setup documentation](https://github.com/graiola/garmin-connect-mcp/blob/master/README.md).
For support, open a repository issue containing only sanitized diagnostics—no
keys, tokens, personal measurements, activity notes or captured responses.
