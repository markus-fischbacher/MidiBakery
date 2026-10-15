"""The Remote Script starts the API with Live (launcher.json) and stops what it started."""

import json
import socket
import sys

from MidiBakery.launcher import ApiLauncher, launcher_path

from midibakery.cli import main

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


def test_install_script_writes_and_removes_the_launcher(bridge_env, tmp_path):
    target = tmp_path / "Remote Scripts"
    assert main(["install-script", "--target", str(target), "--api-provider", "lmstudio", "--api-port", "9123"]) == 0
    config = json.loads((bridge_env / "launcher.json").read_text())
    assert config["port"] == 9123
    assert config["command"][1:] == ["-u", "-m", "midibakery.cli", "api", "--provider", "lmstudio", "--port", "9123"]
    assert (target / "MidiBakery" / "launcher.py").exists()

    assert main(["install-script", "--target", str(target), "--no-api"]) == 0
    assert not (bridge_env / "launcher.json").exists()
