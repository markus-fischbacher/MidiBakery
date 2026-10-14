"""Control surface object Live talks to, and the main-thread executor.

Live calls update_display() on its main thread roughly every 100 ms. That is
the only place where the Live Object Model is touched: queued jobs are
executed there within a small time budget so Live's UI stays responsive.
"""

import threading
import time
import traceback

from . import ops  # noqa: F401  (registers handlers)
from .protocol import ErrorCode, OpError, load_manifest, validate
from .registry import HANDLERS, Context
from .server import BridgeServer

# Max wall time per update_display tick spent on jobs.
TICK_BUDGET_SECONDS = 0.03


def _live_version():
    try:
        import Live

        app = Live.Application.get_application()
        return (app.get_major_version(), app.get_minor_version(), app.get_bugfix_version())
    except Exception:
        return (0, 0, 0)


class MidiShowerSurface(object):
    def __init__(self, c_instance):
        self._c_instance = c_instance
        self._main_thread = threading.get_ident()
        self._live_version = _live_version()
        self._manifest = load_manifest()

        supported = []
        for name, spec in sorted(self._manifest["ops"].items()):
            if name not in HANDLERS:
                self.log("manifest op without handler: %s" % name)
            elif tuple(spec["min_live"]) <= self._live_version:
                supported.append(name)
        self._ctx = Context(c_instance.song(), self._live_version, self.log, supported)

        self._server = BridgeServer(self._live_version, self.log)
        try:
            self._server.start()
            self.show_message("MidiShower ready on port %d" % self._server.port)
        except Exception as exc:
            self.log("could not start bridge: %s" % exc)
            self.show_message("MidiShower: bridge failed to start (%s)" % exc)

    # ------------------------------------------------------------------
    # Executor (main thread only)
    # ------------------------------------------------------------------

    def update_display(self):
        started = time.monotonic()
        jobs = self._server.jobs
        while time.monotonic() - started < TICK_BUDGET_SECONDS:
            try:
                job = jobs.get_nowait()
            except Exception:
                return
            self._run_job(job)

    def _run_job(self, job):
        if not job.client.alive:
            return
        if time.monotonic() > job.deadline:
            job.client.fail(job.id, OpError(ErrorCode.TIMEOUT, "Request expired before Live could run it"))
            return
        try:
            result = self.execute(job.op, job.params)
        except OpError as err:
            job.client.fail(job.id, err)
        except Exception as exc:
            self.log("op %s failed:\n%s" % (job.op, traceback.format_exc()))
            job.client.fail(job.id, OpError(ErrorCode.LIVE_ERROR, str(exc) or exc.__class__.__name__, op=job.op))
        else:
            job.client.reply(job.id, result)

    def execute(self, op_name, params, in_batch=False):
        """Validate and run one op. Write ops are wrapped in their own undo step,
        except inside a batch, which owns a single undo step for all its ops."""
        assert threading.get_ident() == self._main_thread, "LOM access off Live's main thread"
        spec = validate(self._manifest, op_name, params)
        if op_name not in self._ctx.supported_ops:
            raise OpError(
                ErrorCode.UNSUPPORTED,
                "'%s' needs Live %s or newer" % (op_name, ".".join(str(v) for v in spec["min_live"])),
            )
        handler = HANDLERS[op_name]
        if op_name == "batch":
            if in_batch:
                raise OpError(ErrorCode.INVALID_PARAMS, "Batches cannot be nested")
            return handler(self._ctx, params, lambda name, p: self.execute(name, p, in_batch=True))
        if spec["read_only"] or op_name == "history.step" or in_batch:
            return handler(self._ctx, params)
        song = self._ctx.song
        song.begin_undo_step()
        try:
            return handler(self._ctx, params)
        finally:
            song.end_undo_step()

    # ------------------------------------------------------------------
    # Interface Live expects from a control surface
    # ------------------------------------------------------------------

    def disconnect(self):
        self._server.stop()

    def log(self, message):
        self._c_instance.log_message("MidiShower: " + str(message))

    def show_message(self, message):
        self._c_instance.show_message(str(message))

    def song(self):
        return self._c_instance.song()

    def application(self):
        import Live

        return Live.Application.get_application()

    def connect_script_instances(self, instanciated_scripts):
        pass

    def refresh_state(self):
        pass

    def build_midi_map(self, midi_map_handle):
        pass

    def receive_midi(self, midi_bytes):
        pass

    def port_settings_changed(self):
        pass

    def suggest_input_port(self):
        return ""

    def suggest_output_port(self):
        return ""

    def suggest_map_mode(self, cc_no, channel):
        return -1

    def suggest_needs_takeover(self, cc_no, channel):
        return True

    def supports_pad_translation(self):
        return False

    def can_lock_to_devices(self):
        return False

    def lock_to_device(self, device):
        pass

    def unlock_from_device(self, device):
        pass

    def toggle_lock(self):
        pass

    def restore_bank(self, bank_index):
        pass

    def instance_identifier(self):
        return self._c_instance.instance_identifier()
