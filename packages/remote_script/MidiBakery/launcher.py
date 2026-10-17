"""Starts the MidiBakery API with Live and stops it again when Live quits.

The API needs Python 3.12 and third-party packages, so it cannot run inside
Live. `midibakery install` writes launcher.json with the command to run;
without that file nothing is started. An API that already answers on the port
(started by hand, or left over from a crash) is used as it is and never stopped,
unless it is another version of MidiBakery (one from before an update): that one is
stopped and this version's started.
"""

import json
import os
import signal
import socket
import subprocess
import threading
import time
import urllib.request

from .protocol import BRIDGE_VERSION
from .server import config_dir

STOP_TIMEOUT = 3.0
HEALTH_TIMEOUT = 6.0  # the API asks this Live for its health too, which waits while Live starts up


def launcher_path():
    return os.path.join(config_dir(), "launcher.json")


def port_in_use(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


class ApiLauncher(object):
    def __init__(self, log):
        self._log = log
        self._process = None
        self._lock = threading.Lock()
        self._stopped = False

    def start(self):
        """Returns at once; the check and the launch run on a background thread."""
        threading.Thread(target=self._start, name="MidiBakery-launcher", daemon=True).start()

    def _start(self):
        try:
            with open(launcher_path()) as fh:
                config = json.load(fh)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            self._log("launcher.json unreadable: %s" % exc)
            return
        port = int(config.get("port", 8766))
        if port_in_use(port) and not self._stop_other_version(port):
            return
        try:
            log = open(os.path.join(config_dir(), "api.log"), "ab")
            with self._lock:
                if self._stopped:
                    return
                self._process = subprocess.Popen(
                    config["command"],
                    cwd=config.get("cwd") or None,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            log.close()
            self._log("started API (pid %d) on port %d" % (self._process.pid, port))
        except (OSError, KeyError, TypeError) as exc:
            self._log("could not start API: %s" % exc)

    def _stop_other_version(self, port):
        """True when the API on the port was another version and is gone now, so ours can start."""
        try:
            with open(os.path.join(config_dir(), "api.json")) as fh:
                info = json.load(fh)
            request = urllib.request.Request(
                "http://127.0.0.1:%d/health" % port, headers={"Authorization": "Bearer %s" % info["token"]}
            )
            with urllib.request.urlopen(request, timeout=HEALTH_TIMEOUT) as response:
                health = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # not ours, a stale api.json, no answer: leave it
            self._log("API already running on port %d (%s)" % (port, exc))
            return False
        version = health.get("version")
        if version == BRIDGE_VERSION:
            self._log("API %s already running on port %d" % (version, port))
            return False
        pid = health.get("pid")
        if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
            self._log("API %s on port %d is not version %s; quit it and restart Live" % (version, port, BRIDGE_VERSION))
            return False
        self._log("stopping API %s (pid %d) on port %d: this is version %s" % (version, pid, port, BRIDGE_VERSION))
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            self._log("could not stop API %s: %s" % (version, exc))
            return False
        deadline = time.monotonic() + 2 * STOP_TIMEOUT
        while time.monotonic() < deadline:
            if not port_in_use(port):
                return True
            time.sleep(0.1)
        self._log("API %s did not stop; port %d still in use" % (version, port))
        return False

    def stop(self):
        with self._lock:
            self._stopped = True
            process = self._process
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
