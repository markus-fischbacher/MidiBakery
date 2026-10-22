"""`midibakery install` / `uninstall`: where Live's User Library is, what goes there, and that updates and
uninstalls touch only what MidiBakery wrote."""

import json
import shutil
import sys
from pathlib import Path

import pytest

from midibakery import __version__, install
from midibakery.cli import main

LIBRARY_CFG = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12.0_12402" Creator="Ableton Live 12.4.6">
\t<ContentLibrary>
\t\t<UserLibrary>
\t\t\t<LibraryProject Id="0">
\t\t\t\t<ProjectLocation />
\t\t\t\t<ProjectName Value="User Library" />
\t\t\t\t<ProjectPath Value="{path}" />
\t\t\t</LibraryProject>
\t\t</UserLibrary>
\t</ContentLibrary>
</Ableton>
"""


@pytest.fixture(scope="module")
def payload():
    return install.repo_payload()


def _files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_library_cfg_names_the_user_library(tmp_path):
    cfg = tmp_path / "Library.cfg"
    cfg.write_text(LIBRARY_CFG.format(path="/Volumes/Studio/Ableton"))
    assert install.library_from_config(cfg) == Path("/Volumes/Studio/Ableton/User Library")
    cfg.write_text("<Ableton><ContentLibrary /></Ableton>")
    assert install.library_from_config(cfg) is None
    cfg.write_text("not xml")
    assert install.library_from_config(cfg) is None
    assert install.library_from_config(tmp_path / "missing.cfg") is None


def test_the_newest_lives_library_wins(tmp_path, monkeypatch):
    monkeypatch.setattr(install.sys, "platform", "darwin")
    monkeypatch.setattr(install.Path, "home", lambda: tmp_path)
    prefs = tmp_path / "Library/Preferences/Ableton"
    for version, library in (("Live 12.4.5", "/old"), ("Live 12.10.1", "/new"), ("Live 12.4.6", "/mid")):
        (prefs / version).mkdir(parents=True)
        (prefs / version / "Library.cfg").write_text(LIBRARY_CFG.format(path=library))
    assert install.user_library() == Path("/new/User Library")  # 12.10 is newer than 12.4
    shutil.rmtree(prefs)
    assert install.user_library() == tmp_path / "Music/Ableton/User Library"  # no Live settings: the default


def test_install_puts_the_remote_script_and_every_device_in_place(bridge_env, tmp_path, payload):
    library = tmp_path / "User Library"
    record = install.install(library, payload)
    script = library / "Remote Scripts/MidiBakery"
    assert (script / "__init__.py").exists() and (script / "manifest.json").exists()
    assert not list(script.rglob("__pycache__"))
    listed = json.loads((payload.devices / "install.json").read_text())["files"]
    for entry in listed:
        assert (library / entry["target"]).read_bytes() == (payload.devices / entry["source"]).read_bytes()
    assert (library / "Presets/MIDI Effects/Max MIDI Effect/MidiBakery/MidiBakery Chat.amxd").exists()
    assert (library / "Presets/Audio Effects/Max Audio Effect/MidiBakery/midibakery-about.js").exists()
    assert record["version"] == __version__
    assert json.loads((bridge_env / "installed.json").read_text()) == record


def test_an_update_removes_what_the_new_version_no_longer_has(bridge_env, tmp_path, payload):
    library = tmp_path / "User Library"
    install.install(library, payload)
    # the next version renamed the Reference Analyzer
    newer = tmp_path / "newer"
    shutil.copytree(payload.devices, newer)
    shutil.move(newer / "audio_effect/MidiBakery Reference Analyzer.amxd", newer / "audio_effect/MidiBakery Reference Pro.amxd")
    listing = json.loads((newer / "install.json").read_text())
    for entry in listing["files"]:
        for key in ("source", "target"):
            entry[key] = entry[key].replace("MidiBakery Reference Analyzer", "MidiBakery Reference Pro")
    (newer / "install.json").write_text(json.dumps(listing))

    install.install(library, install.Payload(payload.remote_script, newer))
    folder = library / "Presets/Audio Effects/Max Audio Effect/MidiBakery"
    assert (folder / "MidiBakery Reference Pro.amxd").exists()
    assert not (folder / "MidiBakery Reference Analyzer.amxd").exists()


def test_a_moved_library_takes_everything_along(bridge_env, tmp_path, payload):
    old, new = tmp_path / "old", tmp_path / "new"
    install.install(old, payload)
    (old / "Samples").mkdir()
    (old / "Samples/kick.wav").write_bytes(b"mine")
    install.install(new, payload)
    assert _files(old) == {"Samples/kick.wav"}
    assert (new / "Remote Scripts/MidiBakery/__init__.py").exists()


def test_uninstall_removes_only_what_install_wrote(bridge_env, tmp_path, payload):
    library = tmp_path / "User Library"
    tools = library / "MIDI Tools/Max Generators"
    tools.mkdir(parents=True)
    (tools / "Someone Else's Generator.amxd").write_bytes(b"theirs")
    (library / "Remote Scripts/Other").mkdir(parents=True)
    install.install(library, payload)
    install.write_launcher("anthropic", None, 8766)
    # Live drops its folder info into browser folders
    (library / "Presets/MIDI Effects/Max MIDI Effect/MidiBakery" / install.FOLDER_INFO).mkdir()

    removed = install.uninstall()
    assert removed
    assert _files(library) == {"MIDI Tools/Max Generators/Someone Else's Generator.amxd"}
    assert (library / "Remote Scripts/Other").is_dir()
    assert not (library / "Presets/MIDI Effects/Max MIDI Effect/MidiBakery").exists()
    assert not (bridge_env / "launcher.json").exists() and not (bridge_env / "installed.json").exists()
    assert install.uninstall() == []  # twice is fine


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need extra rights on Windows; --link is for development")
def test_link_points_the_remote_script_at_the_sources(bridge_env, tmp_path, payload):
    library = tmp_path / "User Library"
    install.install(library, payload, link=True)
    script = library / "Remote Scripts/MidiBakery"
    assert script.is_symlink() and script.resolve() == payload.remote_script.resolve()
    install.uninstall()
    assert not script.is_symlink() and payload.remote_script.exists()


def test_the_launcher_runs_the_packaged_app_itself(bridge_env, monkeypatch):
    install.write_launcher("lmstudio", "qwen", 9123)
    config = json.loads((bridge_env / "launcher.json").read_text())
    assert config["command"][1:4] == ["-u", "-m", "midibakery.cli"] and config["cwd"] == str(install.REPO_ROOT)
    assert config["version"] == __version__ and config["port"] == 9123

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "/Apps/MidiBakery/runtime/0.2.0/midibakery")
    install.write_launcher("lmstudio", "qwen", 9123)
    config = json.loads((bridge_env / "launcher.json").read_text())
    assert config["command"] == ["/Apps/MidiBakery/runtime/0.2.0/midibakery", "api", "--provider", "lmstudio", "--port", "9123", "--model", "qwen"]
    assert "cwd" not in config


def test_an_update_clears_the_older_runtimes(tmp_path):
    runtime = tmp_path / "runtime"
    for name in ("0.1.0", "0.2.0", "0.3.0", "logs"):
        (runtime / name).mkdir(parents=True)
    (runtime / "0.1.0" / "midibakery").write_bytes(b"old")
    assert sorted(p.name for p in install.prune_runtimes(runtime / "0.3.0")) == ["0.1.0", "0.2.0"]
    assert sorted(p.name for p in runtime.iterdir()) == ["0.3.0", "logs"]


def test_the_cli_installs_and_uninstalls(bridge_env, tmp_path, capsys):
    library = tmp_path / "User Library"
    assert main(["install", "--library", str(library), "--api-provider", "lmstudio", "--api-port", "9123"]) == 0
    assert (library / "Remote Scripts/MidiBakery/launcher.py").exists()
    assert json.loads((bridge_env / "launcher.json").read_text())["port"] == 9123
    assert main(["install", "--library", str(library), "--no-api"]) == 0
    assert not (bridge_env / "launcher.json").exists()
    assert main(["uninstall"]) == 0
    assert not (library / "Remote Scripts/MidiBakery").exists()
    assert f"installed MidiBakery {__version__}" in capsys.readouterr().out


def test_an_update_keeps_the_apis_settings(bridge_env, tmp_path):
    library = tmp_path / "User Library"

    def launched():
        return install.launcher_settings()

    assert main(["install", "--library", str(library)]) == 0
    assert launched() == {"provider": "anthropic", "model": None, "port": 8766}
    assert main(["install", "--library", str(library), "--api-provider", "lmstudio", "--api-model", "qwen", "--api-port", "9123"]) == 0
    assert main(["install", "--library", str(library)]) == 0  # the update (what the installers run)
    assert launched() == {"provider": "lmstudio", "model": "qwen", "port": 9123}
    assert main(["install", "--library", str(library), "--api-provider", "ollama"]) == 0
    assert launched() == {"provider": "ollama", "model": None, "port": 9123}  # lmstudio's model is no ollama model

    assert main(["install", "--library", str(library), "--no-api"]) == 0
    assert main(["install", "--library", str(library)]) == 0
    assert launched() is None  # still off
    assert main(["install", "--library", str(library), "--api-provider", "anthropic"]) == 0
    assert launched() == {"provider": "anthropic", "model": None, "port": 8766}


def test_settings_of_an_older_launcher_json_are_read_from_its_command(bridge_env):
    (bridge_env / "launcher.json").write_text(json.dumps({
        "command": ["/x/python", "-u", "-m", "midibakery.cli", "api", "--provider", "lmstudio", "--port", "8766", "--model", "gemma"],
        "cwd": "/x", "port": 8766}))
    assert install.launcher_settings() == {"provider": "lmstudio", "model": "gemma", "port": 8766}
    assert install.api_settings() == {"provider": "lmstudio", "model": "gemma", "port": 8766}


def test_the_app_uninstalls_itself_too(bridge_env, tmp_path, payload, monkeypatch):
    runtime = tmp_path / "MidiBakery/runtime"
    app = runtime / "0.2.0"
    app.mkdir(parents=True)
    (app / "midibakery").write_bytes(b"app")
    assert install.app_runtime() is None  # from the checkout: no app folder to remove
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(app / "midibakery"))
    assert install.app_runtime() == runtime
    install.install(tmp_path / "User Library", payload)
    removed = install.uninstall(runtime=install.app_runtime())
    assert runtime in removed and not runtime.exists()
