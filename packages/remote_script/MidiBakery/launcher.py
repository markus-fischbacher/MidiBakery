"""Starts the MidiBakery API with Live and stops it again when Live quits.

The API needs Python 3.12 and third-party packages, so it cannot run inside
Live. `midibakery install-script` writes launcher.json with the command to run;
without that file nothing is started. An API that already answers on the port
(started by hand, or left over from a crash) is used as it is and never stopped.
"""

import json
import os
import socket
import subprocess
import threading

from .server import config_dir

STOP_TIMEOUT = 3.0


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
        if port_in_use(port):
            self._log("API already running on port %d" % port)
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
