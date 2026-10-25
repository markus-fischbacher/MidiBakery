# MidiBakery

By Klirrwerk. EDM song sketches for inspiration in Ableton Live 12 Suite: from genre recipes, from imported Live Sets and from analyzed reference songs.

## Install

MidiBakery is free of charge. You need **Ableton Live 12 Suite** (12.3 or newer, with Max for Live) on **macOS** or **Windows 64-bit**. No Python or other tools.

1. Download the installer from the [latest release](https://github.com/markus-fischbacher/MidiBakery/releases/latest): `MidiBakery-<version>-macos-arm64.pkg` (Apple Silicon), `-macos-x64.pkg` (Intel) or `-windows-x64-setup.exe`.
2. Close Live and run the installer. It installs for your user only, no administrator password. Not signed yet: macOS **System Settings > Privacy & Security > Open Anyway**, Windows **More info > Run anyway**.
3. Start Live. In **Settings > Link, Tempo & MIDI > Control Surface** choose **MidiBakery** (Input and Output stay *None*).
4. In the browser, **User Library**: drag **MidiBakery Bake** onto a MIDI track, pick a genre, click **Bake**. That is your first song. Also there: **Chat**, **Set Importer**, **Reference Analyzer**.
5. For the chat, add a Claude API key (**Key** button in the Chat device) or use a local model. For Claude Desktop or Claude Code, see the MCP server guide (set `MIDIBAKERY_CONFIRM=chat` if a confirmation is declined).

Details, updates, uninstall and troubleshooting: [User Guide](docs/user/USER_GUIDE.md) (English), [Benutzerhandbuch](docs/user/BENUTZERHANDBUCH.md) (Deutsch).

**Deutsch, kurz:** Installer von der [Releases-Seite](https://github.com/markus-fischbacher/MidiBakery/releases/latest) laden (macOS `.pkg`, Windows `-setup.exe`), Live schließen, Installer ausführen (nicht signiert: macOS „Dennoch öffnen“, Windows „Trotzdem ausführen“), Live starten, unter **Einstellungen > Link, Tempo & MIDI > Control Surface** **MidiBakery** wählen, dann **MidiBakery Bake** aus der User Library auf eine MIDI-Spur ziehen und **Bake** klicken. Alles Weitere im [Benutzerhandbuch](docs/user/BENUTZERHANDBUCH.md).

## Documentation

| For | Document |
|---|---|
| Musicians (German): install, set up, use | [docs/user/BENUTZERHANDBUCH.md](docs/user/BENUTZERHANDBUCH.md) |
| Musicians (English) | [docs/user/USER_GUIDE.md](docs/user/USER_GUIDE.md) |
| MCP server for Claude Desktop / Claude Code: setup and the 16 tools (German: [MCP_SERVER.de.md](docs/user/MCP_SERVER.de.md)) | [docs/user/MCP_SERVER.md](docs/user/MCP_SERVER.md) |
| How the Remote Script, the core (MCP server, API, agent) and the Max for Live devices work together | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Genre recipes behind `plan_song` | [docs/GENRES.md](docs/GENRES.md) |
| Named patterns for `compose` (bass, lead, techno drums, emotion progressions) | [docs/PATTERNS.md](docs/PATTERNS.md) |
| Changes per version | [CHANGELOG.md](CHANGELOG.md) |
| Update service | [services/updates/README.md](services/updates/README.md) |

## Layout

| Path | What |
|---|---|
| `packages/core` | `midibakery` Python package: op catalog, bridge client, composition engine (`compose/`), Live Set reader (`als/`), agent loop (`agent/`), local API for Max for Live (`api/`), MCP server, CLI |
| `packages/remote_script/MidiBakery` | Remote Script loaded by Live (stdlib only, Python 3.11) |
| `packages/m4l` | Max for Live devices: build script and sources (Bake, Chat, Set Importer, Reference Analyzer) |
| `packaging/` | Packaged app (PyInstaller), macOS .pkg, Windows setup, release tools (signed update manifest) |
| `services/updates` | Update service: Cloudflare Worker + R2 on `updates.klirrwerk.com` |
| `tests/` | Contract tests: real Remote Script + fake Live Object Model over a real socket |

## Development

```bash
uv sync
uv run pytest
uv run midibakery manifest          # after changing the catalog
uv run midibakery install --link    # Remote Script (symlinked), devices and the API's launch into Live
uv run midibakery ping              # with Live running and MidiBakery selected as Control Surface
```

### Packaged app

```bash
uv run --group package python packaging/build_app.py  # build/app/midibakery/ + MidiBakery-<version>-<os>-<arch>.zip
python packaging/smoke.py build/app/midibakery        # runs it: install/uninstall, API, MCP server
```

PyInstaller freezes `midibakery` with its Python and the payload (Remote Script, built devices) into one
folder; `midibakery install` from there installs into Live like from the checkout. It builds for the system it
runs on: CI (`.github/workflows/package.yml`) builds and smoke-tests macOS (Apple silicon) and Windows.

```bash
python packaging/macos/build_pkg.py   # build/app/MidiBakery-<version>-macos-arm64.pkg, -macos-x64.pkg on Intel (not signed yet)
```

The macOS installer installs for the current user, no administrator: the app into
`~/Library/Application Support/MidiBakery/runtime/<version>/`, then its postinstall runs `midibakery install`.
Installing a newer package updates and keeps the API's settings; `.../runtime/<version>/midibakery uninstall`
removes the app, the Remote Script, the devices and the package receipt. CI installs and uninstalls it on macOS;
the Intel package is built and tested on release tags and on PRs labelled `intel`.

```bash
python packaging/windows/build_setup.py   # on Windows, with Inno Setup 6: build/app/MidiBakery-<version>-windows-x64-setup.exe
```

The Windows setup does the same for the current user, no administrator: the app into
`%LOCALAPPDATA%\Programs\MidiBakery\runtime\<version>\`, then `midibakery install`. Running a newer setup updates;
its uninstaller (Settings > Apps) runs `midibakery uninstall` and removes the app. CI installs, updates and
uninstalls it on Windows. Neither installer is signed yet.

### Updates

The installer is the updater. The running API asks `updates.klirrwerk.com` once a day whether a newer
version exists; the devices' About line and the Chat device then show it, and *Install* in the Chat device
downloads the installer, checks it against the release's Ed25519-signed manifest and opens it.
`midibakery update` does the same from the terminal (`--check` only asks, `--disable` turns the daily check off).
A tag `v<version>` builds the installers and publishes them to the update service; setup and details in [services/updates/README.md](services/updates/README.md).

## License

Proprietary, all rights reserved. The source is publicly visible, but no right to use, copy, modify or distribute it is granted; see [LICENSE](LICENSE). Ableton and Ableton Live are trademarks of Ableton AG; this project is not affiliated with Ableton.
