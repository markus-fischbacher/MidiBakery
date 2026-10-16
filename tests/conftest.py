"""Runs the real Remote Script against the fake LOM on a simulated Live main thread."""

import queue
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fake_live"))
sys.path.insert(0, str(ROOT / "packages" / "remote_script"))

import Live  # noqa: E402  (fake)
import Live.Application  # noqa: E402
from fake_song import CInstance, Song  # noqa: E402

TICK_SECONDS = 0.005


class LiveHarness:
    """A thread that plays Live's main thread: builds the surface, then ticks update_display()."""

    def __init__(self, version=(12, 4, 6)):
        self.version = version
        self._calls: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        self._stop = threading.Event()
        self.paused = threading.Event()
        self.error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        if not self._ready.wait(5):
            raise RuntimeError("fake Live did not start")
        if self.error:
            raise self.error
        return self

    def stop(self):
        self.on_main(lambda: self.surface.disconnect())
        self._stop.set()
        self._thread.join(5)
        Live.MAIN_THREAD["ident"] = None

    def on_main(self, fn):
        """Run fn on the fake main thread (the only thread allowed to touch the LOM)."""
        done: queue.Queue = queue.Queue()
        self._calls.put((fn, done))
        ok, value = done.get(timeout=5)
        if not ok:
            raise value
        return value

    def _run(self):
        try:
            Live.MAIN_THREAD["ident"] = threading.get_ident()
            Live.Application.VERSION["value"] = self.version
            import MidiBakery

            self.song = Song()
            self.c_instance = CInstance(self.song)
            self.surface = MidiBakery.create_instance(self.c_instance)
        except BaseException as exc:  # surface start-up failure
            self.error = exc
            self._ready.set()
            return
        self._ready.set()
        while not self._stop.is_set():
            while True:
                try:
                    fn, done = self._calls.get_nowait()
                except queue.Empty:
                    break
                try:
                    done.put((True, fn()))
                except BaseException as exc:
                    done.put((False, exc))
            if not self.paused.is_set():
                self.song.tick()
                self.surface.update_display()
            time.sleep(TICK_SECONDS)


@pytest.fixture
def bridge_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDIBAKERY_HOME", str(tmp_path))
    monkeypatch.setenv("MIDIBAKERY_PORT", "0")
    return tmp_path


@pytest.fixture
def live(bridge_env):
    harness = LiveHarness().start()
    yield harness
    harness.stop()


@pytest.fixture
async def client(live):
    from midibakery.bridge import BridgeClient

    c = BridgeClient()
    yield c
    await c.close()
