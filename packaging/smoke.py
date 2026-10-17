"""Runs the packaged app the way users and Live will: version, install/uninstall from its own payload,
the API (health, chat page) and the MCP server over stdio. Standard library only, any Python.

    python packaging/smoke.py build/app/midibakery
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def expected_version() -> str:
    import re

    text = (ROOT / "packages/core/src/midibakery/__init__.py").read_text(encoding="utf-8")
    return re.search(r'^__version__ = "([^"]+)"', text, re.M)[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAILED: {message}")
    print(f"ok  {message}")


def main(app_dir: str) -> int:
    app = Path(app_dir).resolve()
    exe = app / ("midibakery.exe" if sys.platform == "win32" else "midibakery")
    version = expected_version()
    home = Path(tempfile.mkdtemp(prefix="midibakery-smoke-"))
    env = {**os.environ, "MIDIBAKERY_HOME": str(home / "config"), "MIDIBAKERY_PORT": "0"}

    def run(*args: str) -> subprocess.CompletedProcess:
        result = subprocess.run([str(exe), *args], env=env, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise SystemExit(f"FAILED: midibakery {' '.join(args)}\n{result.stdout}\n{result.stderr}")
        return result

    check(run("--version").stdout.strip() == f"MidiBakery {version}", f"--version says {version}")

    library = home / "User Library"
    run("install", "--library", str(library), "--no-api")
    payload = app / "_internal" / "payload"
    listing = json.loads((payload / "devices" / "install.json").read_text(encoding="utf-8"))
    check(listing["version"] == version, "the payload's devices have this version")
    check((library / "Remote Scripts/MidiBakery/__init__.py").exists(), "Remote Script installed")
    check((library / "Remote Scripts/MidiBakery/manifest.json").exists(), "Remote Script has its manifest")
    missing = [e["target"] for e in listing["files"] if not (library / e["target"]).is_file()]
    check(not missing, f"all {len(listing['files'])} device files installed {missing or ''}")
    record = json.loads((home / "config/installed.json").read_text())
    check(record["version"] == version, "installed.json records the version")

    port = free_port()
    run("install", "--library", str(library), "--api-provider", "lmstudio", "--api-port", str(port))
    launcher = json.loads((home / "config/launcher.json").read_text())
    check(Path(launcher["command"][0]) == exe and launcher["command"][1] == "api", "launcher.json starts this app's API")

    api = subprocess.Popen([str(exe), "api", "--provider", "lmstudio", "--port", str(port)], env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        info_path = home / "config/api.json"
        deadline = time.monotonic() + 60
        info = None
        while time.monotonic() < deadline and api.poll() is None:
            try:
                info = json.loads(info_path.read_text())
                if info.get("port") == port:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(0.2)
        check(api.poll() is None and info and info.get("port") == port, "the API starts and writes api.json")
        headers = {"Authorization": f"Bearer {info['token']}"}
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/health", headers=headers), timeout=10) as r:
                    health = json.loads(r.read())
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)
        check(health["version"] == version, f"/health reports {version}")
        check(health["pid"] == api.pid, "/health reports the API's own pid (the launcher stops old APIs by it)")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/ui", timeout=10) as r:
            check("<html" in r.read().decode("utf-8").lower(), "the chat page is packaged")
    finally:
        api.terminate()
        try:
            out, _ = api.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            api.kill()
            out, _ = api.communicate()
        if "Traceback" in (out or ""):
            print(out)

    mcp = subprocess.Popen([str(exe), "mcp"], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, text=True)
    try:
        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "1"}}}
        mcp.stdin.write(json.dumps(request) + "\n")
        mcp.stdin.flush()
        reply = json.loads(mcp.stdout.readline())
        check(reply.get("result", {}).get("serverInfo", {}).get("version") == version, "the MCP server answers initialize")
    finally:
        mcp.kill()
        mcp.communicate()

    run("uninstall")
    left = [p for p in library.rglob("*") if p.is_file()]
    check(not left, "uninstall leaves nothing behind")
    print(f"smoke test passed: {exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "build/app/midibakery")))
