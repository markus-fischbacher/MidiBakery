"""`midibakery` command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from midibakery import __version__
from midibakery.catalog import manifest
from midibakery.install import REPO_ROOT

SCRIPT_SOURCE = REPO_ROOT / "packages" / "remote_script" / "MidiBakery"
MANIFEST_PATH = SCRIPT_SOURCE / "manifest.json"


def manifest_json() -> str:
    return json.dumps(manifest(), indent=2, sort_keys=True) + "\n"


def cmd_manifest(args: argparse.Namespace) -> int:
    text = manifest_json()
    if args.check:
        if not MANIFEST_PATH.exists() or MANIFEST_PATH.read_text() != text:
            print(f"{MANIFEST_PATH} is out of date; run `midibakery manifest`", file=sys.stderr)
            return 1
        return 0
    MANIFEST_PATH.write_text(text)
    print(f"wrote {MANIFEST_PATH}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    from midibakery import install

    if not install.frozen():
        MANIFEST_PATH.write_text(manifest_json())  # the Remote Script validates against it
    library = Path(args.library) if args.library else install.user_library()
    api = None if args.no_api else install.api_settings(args.api_provider, args.api_model, args.api_port)
    record = install.install(library, install.payload(), link=args.link, api=api is not None)
    print(f"installed MidiBakery {record['version']} into {library} ({len(record['paths'])} paths)")
    if api is None:
        install.remove_launcher()
        print("the API will not start with Live")
    else:
        path = install.write_launcher(api["provider"], api["model"], api["port"])
        print(f"the API ({api['provider']}) starts with Live; log in {path.with_name('api.log')}")
    if install.app_runtime() is not None:  # the installers' layout: runtime/<version>/
        for old in install.prune_runtimes(Path(sys.executable).parent):
            print(f"removed {old}")
    print("Restart Live. First time: choose 'MidiBakery' under Settings > Link, Tempo & MIDI > Control Surface.")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    from midibakery import install

    # macOS has no uninstaller for packages: the app removes itself. On Windows the setup's uninstaller does
    # (a running program's files cannot be deleted there).
    runtime = install.app_runtime() if sys.platform == "darwin" else None
    removed = install.uninstall(purge=args.purge, runtime=runtime)
    if runtime is not None:
        install.forget_pkg_receipt()
    print(f"removed {len(removed)} paths" + (", the settings and the stored API key" if args.purge else ""))
    print("Restart Live to unload the Remote Script.")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    from midibakery import updates

    if args.disable or args.enable:
        updates.set_enabled(bool(args.enable))
        print(f"daily update check {'on' if args.enable else 'off'}")
        return 0
    if not updates.UPDATE_KEYS:
        print("this build has no update key; updates come with the next installer", file=sys.stderr)
        return 1

    async def run() -> int:
        try:
            update = await updates.check(force=True)
            if not update.available:
                print(f"MidiBakery {__version__} is up to date (newest: {update.version})")
                return 0
            print(f"MidiBakery {update.version} is available (installed: {__version__})")
            if update.notes:
                print(update.notes)
            if args.check:
                return 0
            path = await updates.download(update)
        except updates.UpdateError as exc:
            print(exc, file=sys.stderr)
            return 1
        print(f"verified {path}; opening the installer")
        updates.open_installer(path)
        return 0

    return asyncio.run(run())


def cmd_license(args: argparse.Namespace) -> int:
    from midibakery import license

    if not license.enabled():
        print("this build needs no license")
        return 0

    async def run() -> int:
        try:
            if args.action == "trial":
                await license.start_trial()
            elif args.action == "activate":
                await license.activate(args.key or input("License key: "))
            elif args.action == "deactivate":
                await license.deactivate()
                print("this computer is deactivated; its seat is free again")
                return 0
        except license.LicenseError as exc:
            print(exc, file=sys.stderr)
            return 1
        state = license.status()
        print(state.message or state.state)
        if state.updates_until:
            print(f"updates included until {state.updates_until}")
        if not state.allowed:
            print(f"buy a license: {license.PURCHASE_URL}")
        return 0 if state.allowed else 1

    return asyncio.run(run())


def cmd_auth(args: argparse.Namespace) -> int:
    from getpass import getpass

    from midibakery import credentials

    if args.action == "set-key":
        key = getpass("Claude API key (input hidden): ").strip()
        try:
            if not credentials.valid_format(key):
                raise credentials.InvalidKey("That does not look like a Claude API key")
            asyncio.run(credentials.verify(key))
            credentials.store().save(key)
        except (credentials.InvalidKey, OSError) as exc:
            print(exc, file=sys.stderr)
            return 1
        print("Key stored. The chat uses it on the next connection; no restart needed.")
    elif args.action == "remove":
        credentials.store().delete()
        print("Key removed.")
    state = credentials.status()
    print(f"Claude: {'configured via ' + state['source'] if state['configured'] else 'no API key'}")
    return 0


def cmd_sound(args: argparse.Namespace) -> int:
    from midibakery.compose import my_sounds

    try:
        if args.part:
            if args.preset:
                my_sounds.save(args.part, None if args.preset == "-" else args.preset)
            elif args.part not in my_sounds.load():
                print(f"{args.part}: the genre's preset")
                return 0
        mine = my_sounds.load()
    except ValueError as exc:
        print(exc)
        return 1
    print("\n".join(f"{part}: {'/'.join(path)}" for part, path in mine.items()) or "No own presets: new tracks get the genre's.")
    return 0


def cmd_ping(args: argparse.Namespace) -> int:
    from midibakery.bridge import BridgeClient, BridgeError

    async def run() -> int:
        client = BridgeClient()
        try:
            print(json.dumps(await client.call("live.health"), indent=2))
            return 0
        except BridgeError as exc:
            print(exc, file=sys.stderr)
            return 1
        finally:
            await client.close()

    return asyncio.run(run())


def cmd_mcp(args: argparse.Namespace) -> int:
    from midibakery.mcp import build_server

    server = build_server()
    if args.http:
        server.run("streamable-http", host="127.0.0.1", port=args.port)
    else:
        server.run("stdio")
    return 0


def _provider_factory(default_kind: str, default_model: str | None):
    from midibakery.agent import make_provider

    def factory(options: dict[str, str]):
        kind = options.get("provider") or default_kind
        model = options.get("model") or (default_model if kind == default_kind else None)
        return make_provider(kind, model)

    return factory


def cmd_api(args: argparse.Namespace) -> int:
    from midibakery.api import serve

    serve(_provider_factory(args.provider, args.model), port=args.port)
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    from midibakery.agent import LOCAL_PROVIDERS, SYSTEM_PROMPT, Agent, ToolHost
    from midibakery.agent.loop import describe_input
    from midibakery.bridge import BridgeClient
    from midibakery.mcp import build_server

    provider = _provider_factory(args.provider, args.model)({})

    async def confirm(message: str) -> bool:
        try:
            answer = await asyncio.to_thread(input, f"\n? {message} [y/N] ")
        except EOFError:  # input closed (piped): never confirm by default
            return False
        return answer.strip().lower() in ("y", "yes", "j", "ja")

    async def emit(event: dict) -> None:
        kind = event["type"]
        if kind == "text":
            print(event["text"], end="", flush=True)
        elif kind == "tool_call":
            print(f"\n  -> {event['name']} {describe_input(event['input'])}", flush=True)
        elif kind == "tool_result" and event["is_error"]:
            print(f"  !! {describe_input(event['result'])}", flush=True)
        elif kind == "error":
            print(f"\n[error] {event['message']}", flush=True)
        elif kind == "done":
            usage = event.get("usage") or {}
            tokens = f"{usage.get('input_tokens', '?')} in / {usage.get('output_tokens', '?')} out"
            if usage.get("cache_read_input_tokens"):
                tokens += f", {usage['cache_read_input_tokens']} cached"
            print(f"\n[{tokens}]", flush=True)

    async def run() -> int:
        bridge = BridgeClient()
        try:
            async with ToolHost(build_server(bridge), confirm) as host:
                agent = Agent(provider, host, SYSTEM_PROMPT, compact=provider.name in LOCAL_PROVIDERS)
                print(f"MidiBakery chat ({provider.name}, {provider.model}, {len(host.tools)} tools). Empty line or Ctrl-D quits, /reset forgets.")
                while True:
                    try:
                        text = await asyncio.to_thread(input, "\n> ")
                    except EOFError:
                        return 0
                    if not text.strip():
                        return 0
                    if text.strip() == "/reset":
                        agent.reset()
                        continue
                    await agent.send(text, emit)
        finally:
            await bridge.close()

    return asyncio.run(run())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="midibakery")
    parser.add_argument("--version", action="version", version=f"MidiBakery {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("mcp", help="run the MCP server (stdio by default)")
    p.add_argument("--http", action="store_true", help="serve Streamable HTTP on 127.0.0.1 instead of stdio")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_mcp)

    for name, helptext in (("chat", "chat with the agent in the terminal"), ("api", "run the local API for the Max for Live devices")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--provider", choices=["anthropic", "ollama", "lmstudio"], default="anthropic")
        p.add_argument("--model", help="default: claude-sonnet-5-5 (anthropic), qwen3:8b (ollama), google/gemma-4-e4b (lmstudio)")
        if name == "chat":
            p.set_defaults(func=cmd_chat)
        else:
            p.add_argument("--port", type=int, default=8766)
            p.set_defaults(func=cmd_api)

    p = sub.add_parser("manifest", help="regenerate the Remote Script op manifest from the catalog")
    p.add_argument("--check", action="store_true", help="fail if the manifest is out of date")
    p.set_defaults(func=cmd_manifest)

    p = sub.add_parser("install", help="install (or update) the Remote Script and the devices into Live's User Library")
    p.add_argument("--link", action="store_true", help="symlink the Remote Script instead of copying it (development)")
    p.add_argument("--library", help="User Library folder (default: the one Live uses)")
    # Unset: what the last install chose (an update keeps it), else anthropic on 8766.
    p.add_argument("--api-provider", choices=["anthropic", "ollama", "lmstudio"], help="provider of the API that starts with Live")
    p.add_argument("--api-model", help="model of the API that starts with Live")
    p.add_argument("--api-port", type=int)
    p.add_argument("--no-api", action="store_true", help="do not start the API with Live")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("uninstall", help="remove what `install` put into Live and the API's launch")
    p.add_argument("--purge", action="store_true", help="also remove the settings, stored analyses and the stored API key")
    p.set_defaults(func=cmd_uninstall)

    p = sub.add_parser("update", help="look for a newer MidiBakery, download its installer and open it")
    p.add_argument("--check", action="store_true", help="only say whether there is one")
    p.add_argument("--disable", action="store_true", help="turn the daily check (in the API) off")
    p.add_argument("--enable", action="store_true", help="turn the daily check back on")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("license", help="show the license; start the trial, activate or deactivate this computer")
    p.add_argument("action", nargs="?", choices=["status", "trial", "activate", "deactivate"], default="status")
    p.add_argument("key", nargs="?", help="for activate: the license key (asked for when left out)")
    p.set_defaults(func=cmd_license)

    p = sub.add_parser("auth", help="manage the Claude API key (in the macOS Keychain or Windows Credential Manager)")
    p.add_argument("action", choices=["set-key", "status", "remove"])
    p.set_defaults(func=cmd_auth)

    p = sub.add_parser("sound", help="the default preset for new tracks of a part (drums, bass, chords, lead); no preset: show or clear")
    p.add_argument("part", nargs="?", help="drums, bass, chords or lead")
    p.add_argument("preset", nargs="?", help='browser path, e.g. "Synth Keys/Light Keys.adg"; "-" clears it')
    p.set_defaults(func=cmd_sound)

    p = sub.add_parser("ping", help="check the connection to Live")
    p.set_defaults(func=cmd_ping)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
