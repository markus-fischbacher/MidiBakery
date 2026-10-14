"""Socket side of the bridge. Never touches the Live Object Model.

Reader threads parse requests and put them on a job queue that Live's main
thread drains (see surface.py). Results come back through a per-client
outbound queue so the main thread never blocks on a socket.
"""

import hmac
import json
import os
import queue
import secrets
import socket
import sys
import threading
import time

from .protocol import BRIDGE_VERSION, MAX_LINE_BYTES, PROTOCOL_VERSION, ErrorCode, OpError, encode

DEFAULT_PORT = 47681
MAX_CLIENTS = 8
MAX_PENDING_JOBS = 256
DEFAULT_TIMEOUT = 5.0
MAX_TIMEOUT = 60.0


def config_dir():
    override = os.environ.get("MIDISHOWER_HOME")
    if override:
        return override
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/MidiShower")
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MidiShower")
    return os.path.expanduser("~/.config/midishower")


class Job(object):
    __slots__ = ("client", "id", "op", "params", "deadline")

    def __init__(self, client, req_id, op, params, deadline):
        self.client = client
        self.id = req_id
        self.op = op
        self.params = params
        self.deadline = deadline


class Client(object):
    def __init__(self, server, sock, address):
        self.server = server
        self.sock = sock
        self.address = address
        self.outbox = queue.Queue()
        self.authenticated = False
        self.alive = True

    def start(self):
        for target in (self._read_loop, self._write_loop):
            thread = threading.Thread(target=target, name="MidiShower-client")
            thread.daemon = True
            thread.start()

    def send(self, message):
        if self.alive:
            self.outbox.put(message)

    def reply(self, req_id, result):
        self.send({"id": req_id, "ok": True, "result": result})

    def fail(self, req_id, error):
        self.send({"id": req_id, "ok": False, "error": error.to_wire()})

    def close(self):
        """Stop accepting work; the writer flushes queued replies, then closes the socket."""
        if not self.alive:
            return
        self.alive = False
        self.outbox.put(None)
        self.server.forget(self)

    def _shutdown_socket(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    def _write_loop(self):
        while True:
            message = self.outbox.get()
            if message is None:
                self._shutdown_socket()
                return
            try:
                self.sock.sendall(encode(message))
            except OSError:
                self.alive = False
                self.server.forget(self)
                self._shutdown_socket()
                return

    def _read_loop(self):
        buffer = b""
        try:
            while self.alive:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        self._handle_line(line)
                if len(buffer) > MAX_LINE_BYTES:
                    self.send({"ok": False, "error": OpError(ErrorCode.BAD_REQUEST, "Line too long").to_wire()})
                    break
        except OSError:
            pass
        finally:
            self.close()

    def _handle_line(self, line):
        try:
            message = json.loads(line.decode("utf-8"))
        except ValueError:
            self.send({"ok": False, "error": OpError(ErrorCode.BAD_REQUEST, "Invalid JSON").to_wire()})
            return
        if not isinstance(message, dict):
            self.send({"ok": False, "error": OpError(ErrorCode.BAD_REQUEST, "Expected an object").to_wire()})
            return

        if not self.authenticated:
            token = message.get("hello")
            if isinstance(token, str) and hmac.compare_digest(token, self.server.token):
                self.authenticated = True
                self.send({
                    "hello": "ok",
                    "protocol": PROTOCOL_VERSION,
                    "bridge": BRIDGE_VERSION,
                    "live": list(self.server.live_version),
                })
            else:
                self.send({"hello": "denied", "error": OpError(ErrorCode.UNAUTHORIZED, "Bad or missing token").to_wire()})
                self.close()
            return

        req_id = message.get("id")
        op = message.get("op")
        if not isinstance(op, str) or req_id is None:
            self.fail(req_id, OpError(ErrorCode.BAD_REQUEST, "Request needs 'id' and 'op'"))
            return
        timeout = message.get("timeout", DEFAULT_TIMEOUT)
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
            timeout = DEFAULT_TIMEOUT
        timeout = max(0.1, min(float(timeout), MAX_TIMEOUT))
        job = Job(self, req_id, op, message.get("params") or {}, time.monotonic() + timeout)
        try:
            self.server.jobs.put_nowait(job)
        except queue.Full:
            self.fail(req_id, OpError(ErrorCode.CONFLICT, "Bridge is busy, retry shortly"))


class BridgeServer(object):
    def __init__(self, live_version, log):
        self.live_version = live_version
        self.log = log
        self.jobs = queue.Queue(maxsize=MAX_PENDING_JOBS)
        self.token = secrets.token_urlsafe(32)
        self._clients = []
        self._lock = threading.Lock()
        self._sock = None
        self._running = False
        self.port = None

    def start(self):
        port = int(os.environ.get("MIDISHOWER_PORT", DEFAULT_PORT))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        sock.listen(MAX_CLIENTS)
        sock.settimeout(0.5)
        self._sock = sock
        self.port = sock.getsockname()[1]
        self._running = True
        self._write_discovery_file()
        thread = threading.Thread(target=self._accept_loop, name="MidiShower-accept")
        thread.daemon = True
        thread.start()
        self.log("listening on 127.0.0.1:%d" % self.port)

    def stop(self):
        self._running = False
        with self._lock:
            clients = list(self._clients)
        for client in clients:
            client.close()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._remove_discovery_file()

    def forget(self, client):
        with self._lock:
            if client in self._clients:
                self._clients.remove(client)

    def broadcast(self, event, data):
        with self._lock:
            clients = [c for c in self._clients if c.authenticated]
        for client in clients:
            client.send({"event": event, "data": data})

    def _accept_loop(self):
        while self._running:
            try:
                conn, address = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self._lock:
                if len(self._clients) >= MAX_CLIENTS:
                    conn.close()
                    continue
                client = Client(self, conn, address)
                self._clients.append(client)
            conn.settimeout(None)
            client.start()

    def _discovery_path(self):
        return os.path.join(config_dir(), "bridge.json")

    def _write_discovery_file(self):
        directory = config_dir()
        if not os.path.isdir(directory):
            os.makedirs(directory)
        path = self._discovery_path()
        tmp = path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({
                "port": self.port,
                "token": self.token,
                "pid": os.getpid(),
                "protocol": PROTOCOL_VERSION,
                "bridge": BRIDGE_VERSION,
                "live": list(self.live_version),
            }, fh)
        os.replace(tmp, path)

    def _remove_discovery_file(self):
        try:
            with open(self._discovery_path(), "r") as fh:
                if json.load(fh).get("token") != self.token:
                    return  # another Live instance owns it now
            os.remove(self._discovery_path())
        except (OSError, ValueError):
            pass
