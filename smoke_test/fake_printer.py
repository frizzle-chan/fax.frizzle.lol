"""
A networked receipt printer that isn't.

escpos.printer.Network is a plain TCP client: connect, sendall, close. So a
socket that reads until EOF and keeps the bytes is a complete stand-in, and what
lands in it is exactly what would have hit the real printer.
"""
import socket
import socketserver
import threading
from typing import List, Optional


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        printer: 'FakePrinter' = self.server.printer  # type: ignore[attr-defined]
        chunks: List[bytes] = []
        # Read to EOF. The app always closes the socket in a finally, so EOF is
        # the only honest "the job is complete" signal -- returning on the first
        # recv would hand back a truncated stream at random.
        while True:
            try:
                chunk = self.request.recv(65536)
            except OSError:
                break
            if not chunk:
                break
            chunks.append(chunk)
        printer._record(b''.join(chunks))


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class FakePrinter:
    """Records every completed print job. Use as a context manager."""

    def __init__(self, host: str = '127.0.0.1') -> None:
        self._server = _Server((host, 0), _Handler)
        self._server.printer = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._lock = threading.Lock()
        self._jobs: List[bytes] = []
        self._job_arrived = threading.Condition(self._lock)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def jobs(self) -> List[bytes]:
        with self._lock:
            return list(self._jobs)

    def _record(self, data: bytes) -> None:
        with self._job_arrived:
            self._jobs.append(data)
            self._job_arrived.notify_all()

    def wait_for_job(self, index: int = 0, timeout: float = 30.0) -> bytes:
        """Block until job `index` has been received in full, or raise."""
        with self._job_arrived:
            if not self._job_arrived.wait_for(lambda: len(self._jobs) > index, timeout=timeout):
                raise TimeoutError(
                    f'no print job #{index} after {timeout}s '
                    f'(received {len(self._jobs)} job(s))')
            return self._jobs[index]

    def start(self) -> 'FakePrinter':
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    def __enter__(self) -> 'FakePrinter':
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()


class JammedPrinter:
    """A printer that never accepts anything, so connecting to it hangs.

    Not a stall on the read side: the sender's socket buffer swallows ~1.5MB
    before it blocks, and a fax is ~44KB, so a printer that accepts and then
    goes quiet doesn't block the app at all. What does block is the connect --
    which is also the real failure mode, `Network.open()` against a printer
    that's off or off-wifi.

    Filling the accept queue and never draining it gets there deterministically:
    further SYNs are dropped and retried by the kernel, so connect() hangs
    rather than being refused.
    """

    # More than the listen backlog, so the queue is definitely full.
    _QUEUE_FILLERS = 8

    def __init__(self, host: str = '127.0.0.1') -> None:
        self._host = host
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((host, 0))
        self._sock.listen(1)
        self._held: List[socket.socket] = []

    @property
    def port(self) -> int:
        return self._sock.getsockname()[1]

    def __enter__(self) -> 'JammedPrinter':
        for _ in range(self._QUEUE_FILLERS):
            filler = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            filler.settimeout(1)
            try:
                filler.connect((self._host, self.port))
            except OSError:
                # Queue is full -- which is the point. Anyone connecting from
                # here on hangs.
                filler.close()
                break
            self._held.append(filler)
        return self

    def __exit__(self, *exc: object) -> None:
        for filler in self._held:
            filler.close()
        self._sock.close()


def free_port(host: str = '127.0.0.1') -> int:
    """Pick a port nothing is listening on. Racy in theory, fine in a container."""
    sock: Optional[socket.socket] = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, 0))
        return sock.getsockname()[1]
    finally:
        if sock is not None:
            sock.close()
