"""The Remote Script starts the API with Live (launcher.json) and stops what it started."""

import json
import socket
import subprocess
import sys
import time

from MidiBakery.launcher import ApiLauncher, launcher_path, port_in_use
from MidiBakery.protocol import BRIDGE_VERSION

SLEEPER = [sys.executable, "-c", "import time; time.sleep(30)"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def write_launcher(command, port):
    with open(launcher_path(), "w") as fh:
        json.dump({"command": command, "port": port}, fh)


def test_without_launcher_file_nothing_starts(bridge_env):
    launcher = ApiLauncher(print)
    launcher._start()
    assert launcher._process is None
    launcher.stop()


def test_starts_the_api_and_stops_it_with_live(bridge_env):
    write_launcher(SLEEPER, free_port())
    launcher = ApiLauncher(print)
    launcher._start()
    process = launcher._process
    assert process is not None and process.poll() is None
    launcher.stop()
    assert process.poll() is not None
    assert (bridge_env / "api.log").exists()


def test_an_api_already_on_the_port_is_left_alone(bridge_env):
    with socket.socket() as running:
        running.bind(("127.0.0.1", 0))
        running.listen()
        write_launcher(SLEEPER, running.getsockname()[1])
        launcher = ApiLauncher(print)
        launcher._start()
    assert launcher._process is None


def test_no_start_after_live_already_quit(bridge_env):
    write_launcher(SLEEPER, free_port())
    launcher = ApiLauncher(print)
    launcher.stop()
    launcher._start()
    assert launcher._process is None


FAKE_API = """
import http.server, json, os, sys
version = sys.argv[2]
class Health(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        ok = self.path == "/health" and self.headers.get("Authorization") == "Bearer secret"
        body = json.dumps({"ok": True, "version": version, "pid": os.getpid()} if ok else {"error": "UNAUTHORIZED"}).encode()
        self.send_response(200 if ok else 401)
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), Health).serve_forever()
"""


def run_fake_api(bridge_env, version):
    """An API of `version` on a free port, with its api.json; returns (process, port)."""
    port = free_port()
    process = subprocess.Popen([sys.executable, "-c", FAKE_API, str(port), version])
    (bridge_env / "api.json").write_text(json.dumps({"port": port, "token": "secret", "version": version}))
    deadline = time.monotonic() + 10
    while not port_in_use(port):
        assert time.monotonic() < deadline, "fake API did not start"
        time.sleep(0.05)
    return process, port


def test_an_api_of_another_version_is_replaced(bridge_env):
    """An API left from before an update would serve the old version until it is stopped by hand."""
    old, port = run_fake_api(bridge_env, "0.0.1")
    try:
        write_launcher(SLEEPER, port)
        launcher = ApiLauncher(print)
        launcher._start()
        assert old.wait(10) is not None  # stopped
        assert launcher._process is not None and launcher._process.poll() is None
        launcher.stop()
    finally:
        old.kill()


def test_an_api_of_this_version_is_used_as_it_is(bridge_env):
    same, port = run_fake_api(bridge_env, BRIDGE_VERSION)
    try:
        write_launcher(SLEEPER, port)
        launcher = ApiLauncher(print)
        launcher._start()
        assert launcher._process is None and same.poll() is None
    finally:
        same.kill()
