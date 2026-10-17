# MidiBakery update service

A Cloudflare Worker on `updates.klirrwerk.com` in front of the R2 bucket `midibakery-releases`.

| Request | Answer |
|---|---|
| `GET /v1/midibakery/latest?channel=stable` | the channel's signed manifest (`midibakery/channels/stable.json` in R2) |
| `GET /v1/midibakery/download/<version>/<installer>` | an installer (`midibakery/releases/<version>/<installer>`) |
| `POST /v1/midibakery/license/trial` `{machine}` | a signed 30-day trial token, one trial per computer |
| `POST /v1/midibakery/license/activate` `{key, machine}` | a signed license token; counts seats (default 2) |
| `POST /v1/midibakery/license/deactivate` `{key, machine}` | frees the computer's seat |

The app (`packages/core/src/midibakery/updates.py`) asks once a day, through the running API. It
trusts a manifest only when one of the keys in `UPDATE_KEYS` signed it (Ed25519), and runs an
installer only when its SHA-256 matches the manifest. The Worker and R2 therefore need no secrets of
their own: whoever could change files there still cannot get an installer run.

Requests carry the installed version, the system, the architecture and the channel, and the
installation's license token when it has one (`Authorization: License <token>`).

## Licensing

A trial (30 days) or a license key becomes a token the Worker signs (`src/tokens.js`, Ed25519) and the
app checks offline (`packages/core/src/midibakery/license.py`): after activation no connection is needed;
the app asks again once a week, so renewals and revocations arrive, and an outage changes nothing.
Without a token the app reads Live and undoes, but generates and edits nothing; a Set is never touched.

D1 (`migrations/`) holds licenses (key only as SHA-256), activations (the app's machine hash) and trials.
Licenses: perpetual, updates for 12 months. With `REQUIRE_LICENSE_FOR_UPDATES = "1"` an installer is
only handed out to a token whose `updates_until` is not before the release date.

Selling by hand until a merchant of record's webhook does it:

    uv run python packaging/release/issue_license.py issue --name "Ada Lovelace" --email ada@example.com
    uv run python packaging/release/issue_license.py renew MB-XXXX-XXXX-XXXX-XXXX
    uv run python packaging/release/issue_license.py revoke MB-XXXX-XXXX-XXXX-XXXX

The app's side: `midibakery license [status|trial|activate KEY|deactivate]`, or the Chat device.

## Releasing

1. Raise `__version__` in `packages/core/src/midibakery/__init__.py` (and `BRIDGE_VERSION`), merge.
2. Tag `v<version>` on main and push the tag. The package workflow builds and tests the installers,
   then (environment `release`):
   - `worker`: tests and deploys the Worker (`wrangler deploy`);
   - `publish`: signs the manifest (`packaging/release/make_manifest.py`), uploads the installers,
     and finally the channel file. From then on installs see the update within a day.

## One-time setup (by you, not by Claude)

1. **Signing key.** `uv run python packaging/release/keygen.py ~/midibakery-signing.key`
   - Put the printed line into `UPDATE_KEYS` in `updates.py` and release that version: only installs
     that know the key check for updates.
   - Keep the key file offline (password manager); it never goes into the repository.
2. **Cloudflare.**
   - R2: create the bucket `midibakery-releases`.
   - API token (My Profile > API Tokens > Create Token) with *Account: Workers Scripts: Edit*,
     *Account: Workers R2 Storage: Edit* and *Zone klirrwerk.com: Workers Routes: Edit*. The first
     deploy creates the custom domain `updates.klirrwerk.com` (`wrangler.toml`).
3. **Licensing** (when you start selling):
   - `uv run python packaging/release/keygen.py --license ~/midibakery-license.key`; the printed line goes
     into `LICENSE_KEYS` in `license.py` and `LICENSE_PUBLIC_KEYS` in `wrangler.toml`.
   - In `services/updates`: `npx wrangler d1 create midibakery`, put its id into `wrangler.toml`
     (uncomment the D1 block), `npx wrangler d1 migrations apply midibakery --remote`,
     `npx wrangler secret put LICENSE_SIGNING_KEY` (the key file's line).
   - A release with `LICENSE_KEYS` filled turns licensing on in the app; `REQUIRE_LICENSE_FOR_UPDATES`
     ties downloads to it.
   - `PURCHASE_URL` in `license.py` points at the shop page.
4. **GitHub.** Settings > Environments > New environment `release` (optionally with required
   reviewers and the tag rule `v*`), and in it the secrets
   - `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`;
   - `MIDIBAKERY_SIGNING_KEY`: the content of the key file.

## Local

    cd services/updates && node --test test/worker.test.js test/licenses.test.js

`npx wrangler dev` serves the Worker against a local R2. `MIDIBAKERY_UPDATE_URL` points the app at
it, e.g. `MIDIBAKERY_UPDATE_URL=http://127.0.0.1:8787/v1/midibakery midibakery update --check`.

Switching the daily check off: `midibakery update --disable` (or `MIDIBAKERY_NO_UPDATE_CHECK=1`).
