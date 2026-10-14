"""`midishower` command line entry point."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

from midishower.catalog import manifest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_SOURCE = REPO_ROOT / "packages" / "remote_script" / "MidiShower"
MANIFEST_PATH = SCRIPT_SOURCE / "manifest.json"


def manifest_json() -> str:
    return json.dumps(manifest(), indent=2, sort_keys=True) + "\n"


def cmd_manifest(args: argparse.Namespace) -> int:
    text = manifest_json()
    if args.check:
        if not MANIFEST_PATH.exists() or MANIFEST_PATH.read_text() != text:
            print(f"{MANIFEST_PATH} is out of date; run `midishower manifest`", file=sys.stderr)
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


def cmd_install(args: argparse.Namespace) -> int:
    MANIFEST_PATH.write_text(manifest_json())
    target_root = Path(args.target) if args.target else _user_remote_scripts()
    target = target_root / "MidiShower"
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
    print("Restart Live, then choose 'MidiShower' under Settings > Link, Tempo & MIDI > Control Surface.")
    return 0


def cmd_ping(args: argparse.Namespace) -> int:
    from midishower.bridge import BridgeClient, BridgeError

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
    from midishower.mcp import build_server

    server = build_server()
    if args.http:
        server.run("streamable-http", host="127.0.0.1", port=args.port)
    else:
        server.run("stdio")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="midishower")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("mcp", help="run the MCP server (stdio by default)")
    p.add_argument("--http", action="store_true", help="serve Streamable HTTP on 127.0.0.1 instead of stdio")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_mcp)

    p = sub.add_parser("manifest", help="regenerate the Remote Script op manifest from the catalog")
    p.add_argument("--check", action="store_true", help="fail if the manifest is out of date")
    p.set_defaults(func=cmd_manifest)

    p = sub.add_parser("install-script", help="install the Remote Script into Live's User Library")
    p.add_argument("--link", action="store_true", help="symlink instead of copy (development)")
    p.add_argument("--target", help="Remote Scripts folder (default: User Library)")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("ping", help="check the connection to Live")
    p.set_defaults(func=cmd_ping)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
