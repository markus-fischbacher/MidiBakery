"""`midibakery` command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

from midibakery.catalog import manifest

REPO_ROOT = Path(__file__).resolve().parents[4]
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


def _user_remote_scripts() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Music/Ableton/User Library/Remote Scripts"
    if sys.platform.startswith("win"):
        return Path.home() / "Documents/Ableton/User Library/Remote Scripts"
    raise SystemExit("Ableton Live only runs on macOS and Windows")


def launcher_command(provider: str, model: str | None, port: int) -> list[str]:
    command = [sys.executable, "-u", "-m", "midibakery.cli", "api", "--provider", provider, "--port", str(port)]
    return command + ["--model", model] if model else command


def _write_launcher(args: argparse.Namespace) -> None:
    """launcher.json tells the Remote Script how to start the API with Live."""
    from midibakery.bridge.client import config_dir

    path = config_dir() / "launcher.json"
    if args.no_api:
        path.unlink(missing_ok=True)
        print("the API will not start with Live")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    config = {"command": launcher_command(args.api_provider, args.api_model, args.api_port), "cwd": str(REPO_ROOT), "port": args.api_port}
    path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"the API ({args.api_provider}) starts with Live; log in {path.with_name('api.log')}")


def cmd_install(args: argparse.Namespace) -> int:
    MANIFEST_PATH.write_text(manifest_json())
    target_root = Path(args.target) if args.target else _user_remote_scripts()
    target = target_root / "MidiBakery"
    target_root.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
    if args.link:
        target.symlink_to(SCRIPT_SOURCE, target_is_directory=True)
    else:
        shutil.copytree(SCRIPT_SOURCE, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"installed Remote Script to {target}")
    _write_launcher(args)
    print("Restart Live, then choose 'MidiBakery' under Settings > Link, Tempo & MIDI > Control Surface.")
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
    from midibakery.agent import LOCAL_PROVIDERS, REDUCED_TOOLS, SMALL_SYSTEM_PROMPT, SMALL_TOOLS, SYSTEM_PROMPT, Agent, ToolHost
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
        small = args.small
        allowed = SMALL_TOOLS if small else REDUCED_TOOLS if args.reduced else None
        try:
            async with ToolHost(build_server(bridge), confirm, allowed) as host:
                agent = Agent(provider, host, SMALL_SYSTEM_PROMPT if small else SYSTEM_PROMPT, compact=provider.name in LOCAL_PROVIDERS)
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
            p.add_argument("--reduced", action="store_true", help="only the core tools")
            p.add_argument("--small", action="store_true", help="the smallest tool set and prompt, for 8k-context models")
            p.set_defaults(func=cmd_chat)
        else:
            p.add_argument("--port", type=int, default=8766)
            p.set_defaults(func=cmd_api)

    p = sub.add_parser("manifest", help="regenerate the Remote Script op manifest from the catalog")
    p.add_argument("--check", action="store_true", help="fail if the manifest is out of date")
    p.set_defaults(func=cmd_manifest)

    p = sub.add_parser("install-script", help="install the Remote Script into Live's User Library")
    p.add_argument("--link", action="store_true", help="symlink instead of copy (development)")
    p.add_argument("--target", help="Remote Scripts folder (default: User Library)")
    p.add_argument("--api-provider", choices=["anthropic", "ollama", "lmstudio"], default="anthropic", help="provider of the API that starts with Live")
    p.add_argument("--api-model", help="model of the API that starts with Live")
    p.add_argument("--api-port", type=int, default=8766)
    p.add_argument("--no-api", action="store_true", help="do not start the API with Live")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("ping", help="check the connection to Live")
    p.set_defaults(func=cmd_ping)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
