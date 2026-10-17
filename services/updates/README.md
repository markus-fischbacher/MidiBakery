# MidiBakery update service

A Cloudflare Worker on `updates.klirrwerk.com` in front of the R2 bucket `midibakery-releases`.

| Request | Answer |
|---|---|
| `GET /v1/midibakery/latest?channel=stable` | the channel's signed manifest (`midibakery/channels/stable.json` in R2) |
| `GET /v1/midibakery/download/<version>/<installer>` | an installer (`midibakery/releases/<version>/<installer>`) |

The app (`packages/core/src/midibakery/updates.py`) asks once a day, through the running API. It
trusts a manifest only when one of the keys in `UPDATE_KEYS` signed it (Ed25519), and runs an
installer only when its SHA-256 matches the manifest. The Worker and R2 therefore need no secrets of
their own: whoever could change files there still cannot get an installer run.

Requests carry the installed version, the system, the architecture and the channel. Sold versions
later add `Authorization: License <key>`; `licensed()` in `src/index.js` is the place to check it.

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
3. **GitHub.** Settings > Environments > New environment `release` (optionally with required
   reviewers and the tag rule `v*`), and in it the secrets
   - `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`;
   - `MIDIBAKERY_SIGNING_KEY`: the content of the key file.

## Local

    cd services/updates && node --test test/worker.test.js

`npx wrangler dev` serves the Worker against a local R2. `MIDIBAKERY_UPDATE_URL` points the app at
it, e.g. `MIDIBAKERY_UPDATE_URL=http://127.0.0.1:8787/v1/midibakery midibakery update --check`.

Switching the daily check off: `midibakery update --disable` (or `MIDIBAKERY_NO_UPDATE_CHECK=1`).
