# Agensi launch guide

Product: **Garmin Connect MCP Assistant** · Version **0.2.0** · Price **Free**

Status: source, listing copy and an upload-package builder are prepared. No Agensi
account, draft, submission, approval or live marketplace installation is claimed.
Do not announce a public listing until Agensi supplies its real URL and the
end-to-end check below has passed.

## 1. Finish the owner-host acceptance check

Use [ACCEPTANCE.md](ACCEPTANCE.md). A successful local `doctor` proves only Garmin
authentication and one activity read; it does not verify the intended AI client.
Test one real read through that client, compare it with Garmin Connect, and record
only pass/fail, client/version and date. Keep personal responses out of the repo.

The synthetic [demonstration](DEMO.md) shows instructed behavior without publishing
private records. It is not evidence of a real-account or Agensi connection.

## 2. Obtain the upload files

### From GitHub Actions

Open the repository's **Actions → Tests** workflow and select a successful run for
the intended commit. Download `agensi-launch-bundle` from its artifacts section.
Extract the outer artifact. It contains:

- `dist/agensi/garmin-connect-mcp-assistant-0.2.0.zip`: the actual skill upload.
- Its `.zip.sha256` checksum.
- `assets/icon.png`: the existing square 512 × 512 logo, uploaded separately.
- `docs/agensi/`: listing copy, metadata, synthetic example and acceptance guide.

Artifacts are retained for 30 days. Run the workflow manually again, or use the
local builder, if an artifact has expired. Availability depends on a successful
workflow run; do not claim an artifact exists from configuration alone.

### Build locally

From the repository root with Python 3.11+:

```bash
python scripts/build_agensi_package.py --check
python scripts/build_agensi_package.py
```

The packaging commands use only the Python standard library. They do not require
a Garmin key, call Garmin, install dependencies, or create an Agensi account.
Each ZIP has exactly six allowlisted text files under one skill folder, including
`SKILL.md`, the MIT license and four references. No executable scripts, server,
environment, fitness records, logo or listing documents are bundled in the skill.

The builder produces deterministic bytes and a SHA-256 checksum. Existing identical
outputs are reused; differing files are not overwritten. During a revision, use a
fresh `--output-dir dist/agensi-revision`, or increment the skill version in
`listing.json` for a new release. Review the changed sources before rebuilding.

**Upload the inner skill ZIP only.** Do not upload the repository ZIP, the outer
Actions artifact, or your local checkout/environment. Agensi must see `SKILL.md`
directly inside the submitted archive, not inside another ZIP.

## 3. Fill the listing

Sign in yourself at [Agensi](https://www.agensi.io/), review its current terms, and
enable **Creator Mode** in Dashboard → Settings. Complete the creator profile.
A free listing does not require a payout method; paid products are out of scope.

Open [Submit a skill](https://www.agensi.io/dashboard/submit). The local
[listing.json](listing.json) is a field checklist, not a supported submission API
payload; do not send it to an invented endpoint.

| Form field | Prepared value/source |
|---|---|
| Name | Garmin Connect MCP Assistant |
| Pricing | Free |
| Version, if offered | 0.2.0 |
| Summary | `summary` in [listing.json](listing.json), under 300 characters |
| Description | Complete [LISTING.md](LISTING.md) |
| Logo | `assets/icon.png` from the repository, uploaded separately |
| See it in action | Request and complete response from [DEMO.md](DEMO.md); retain its synthetic-data disclosure |
| First category | Productivity |
| Other categories | Data & Databases; APIs & Backend |
| Tags and use cases | Corresponding fields in [listing.json](listing.json) |
| Compatibility | `compatibility_note` in [listing.json](listing.json) |
| Documentation | Repository README link in `docs_url` |

Agensi checks name/package uniqueness at submission. If this name is taken,
choose **Garmin Connect MCP Assistant by Gennaro Raiola** as the display name
and update the local listing metadata; do not claim availability before checking.
Keep the skill's stable machine name unchanged unless repackaging is necessary.

### Needs access to

Review the automatically detected permissions and explicitly declare the external
server prerequisite in the appropriate field/service selector. Use this wording:

> Requires a separately installed and configured instance of Gennaro Raiola's
> Garmin Connect MCP, connected to the same AI agent, and the user's own Garmin
> Personal API access. This skill does not host the server or supply credentials.

The public documentation does not establish the exact service-selector values;
check the actual preview rather than inventing a connector ID. Do not advertise
one-click server installation, all-agent compatibility, an OAuth endpoint or a
hosted multi-user product. Verify that any auto-generated text preserves these limits.

### Privacy and licensing review

- Keep the MIT license and public repository link. Agensi explicitly permits
  appropriately licensed open-source skills. Its service delivery terms do not
  make the independently available GitHub source proprietary.
- Do not upload API keys, bearer tokens, personal activity exports or live fixtures.
- Do not send Garmin measurements or private context in Agensi search, feedback,
  submission reasons or listing examples.
- Do not say all data stays on-device: the user's AI provider processes tool results.
- Do not enrol in an affiliate program, add a paid tier or promise paid support as
  part of this free launch. Those require a separate decision and terms review.
- Garmin's Personal API is intended for users accessing their own data. A future
  commercial/hosted offering requires review of Garmin's applicable API agreement;
  selling instructions is not automatically proof of commercial API permission.

## 4. Submit and verify

Review desktop/mobile preview and all permissions. The owner decides whether to
submit for Agensi's security and human review. Allow up to 48 hours according to
the current creator FAQ; approval is not guaranteed.

After approval:

1. Copy the exact live listing URL; do not construct a guessed slug.
2. Load the skill through Agensi in a supported agent that also has the Garmin MCP.
3. Run one minimal real read and verify it. Keep results private.
4. Update this launch status and the README with the actual URL and verified
   client/version. Record the date and check performed in `docs/VERIFICATION.md`.
5. Announce only the capabilities and client combinations actually verified.

## Authoritative references

Checked 5 November 2026; recheck before accepting or submitting changed terms.

- [Creator quickstart](https://www.agensi.io/docs/creator-quickstart)
- [Package your skill](https://www.agensi.io/docs/packaging)
- [Submission fields](https://www.agensi.io/docs/submit-on-the-website)
- [External MCP requirements](https://www.agensi.io/docs/what-you-can-sell)
- [Free/open-source FAQ](https://www.agensi.io/docs/creator-faq)
- [Privacy when using skills](https://www.agensi.io/docs/privacy)
- [Agensi terms](https://www.agensi.io/terms)
- [Garmin Personal API FAQ](https://developer.garmin.com/gc-developer-program/personal/personal-faq/)
- [GitHub workflow artifacts](https://docs.github.com/en/actions/tutorials/store-and-share-data)
