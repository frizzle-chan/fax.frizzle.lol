"""
The whole pipeline, for real: launch the app, POST a fax at it over HTTP, and
check that valid ESC/POS raster data lands on a fake networked printer.

No Discord anywhere. That is the point -- the HTTP source stands in for it, and
is the same door email will come through.
"""
import base64
import math
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Iterator

import pytest
import requests
from PIL import Image

from smoke_test import escpos_stream
from smoke_test.fake_printer import FakePrinter, JammedPrinter, free_port

pytestmark = pytest.mark.smoke

REPO_ROOT = Path(__file__).resolve().parent.parent

PRINTER_PROFILE = 'TM-T88III'
PROFILE_WIDTH = 512
# python-escpos splits any image taller than this into its own GS v 0 block.
FRAGMENT_HEIGHT = 960

TOKEN = 'smoke-test-token-not-a-secret'
STARTUP_TIMEOUT = 60.0
REQUEST_TIMEOUT = 30.0


def png_b64(size=(64, 48), color=(0, 0, 0)) -> str:
    img = Image.new('RGB', size, color)
    stream = BytesIO()
    img.save(stream, 'PNG')
    return base64.b64encode(stream.getvalue()).decode('ascii')


@contextmanager
def running_app(printer_port: int,
                http_port: int,
                log_path: Path,
                printer_timeout: int = 60) -> Iterator[subprocess.Popen]:
    """Run bot.py as a real subprocess, HTTP source only, no Discord token."""
    env = {
        **os.environ,
        'FAX_SOURCES': 'http',
        'FAX_HTTP_HOST': '127.0.0.1',
        'FAX_HTTP_PORT': str(http_port),
        'FAX_HTTP_TOKEN': TOKEN,
        'PRINTER_HOST': '127.0.0.1',
        'PRINTER_PORT': str(printer_port),
        'PRINTER_PROFILE': PRINTER_PROFILE,
        'PRINTER_TIMEOUT': str(printer_timeout),
        'PYTHONUNBUFFERED': '1',
    }
    # Straight to a file rather than a PIPE: nobody is draining a pipe while we
    # poll for readiness, and a chatty failure would fill the buffer and wedge
    # the child (and then the CI job) forever.
    log = log_path.open('wb')
    proc = subprocess.Popen([sys.executable, 'bot.py'],
                            cwd=REPO_ROOT,
                            env=env,
                            stdout=log,
                            stderr=subprocess.STDOUT)
    try:
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
        log.close()
        # Has to be in the finally: an assertion failure propagates out through
        # the yield, so anything after the try block runs only when the test
        # passed -- which is the one time nobody needs this. pytest captures it
        # and shows it only on failure.
        print(f'--- bot.py output ---\n{log_path.read_text(errors="replace")}')


def wait_until_serving(proc: subprocess.Popen, base_url: str, log_path: Path) -> None:
    deadline = STARTUP_TIMEOUT
    step = 0.25
    waited = 0.0
    while waited < deadline:
        if proc.poll() is not None:
            raise AssertionError(
                f'bot.py exited with {proc.returncode} before serving:\n'
                f'{log_path.read_text(errors="replace")}')
        try:
            response = requests.get(f'{base_url}/healthz', timeout=2)
            if response.ok:
                return
        except requests.RequestException:
            pass
        # Cheaper than sleeping: poll() already returned, so just wait.
        try:
            proc.wait(timeout=step)
        except subprocess.TimeoutExpired:
            pass
        waited += step

    raise AssertionError(
        f'bot.py never answered /healthz within {STARTUP_TIMEOUT}s:\n'
        f'{log_path.read_text(errors="replace")}')


@pytest.fixture
def printer() -> Iterator[FakePrinter]:
    with FakePrinter() as fake:
        yield fake


@pytest.fixture
def app(printer: FakePrinter, tmp_path: Path) -> Iterator[str]:
    http_port = free_port()
    log_path = tmp_path / 'bot.log'
    with running_app(printer.port, http_port, log_path) as proc:
        base_url = f'http://127.0.0.1:{http_port}'
        wait_until_serving(proc, base_url, log_path)
        yield base_url


def test_healthz_reports_the_printer_width(app: str) -> None:
    response = requests.get(f'{app}/healthz', timeout=REQUEST_TIMEOUT)

    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'width': PROFILE_WIDTH}


def test_fax_without_a_token_is_rejected_and_never_reaches_the_printer(
        app: str, printer: FakePrinter) -> None:
    response = requests.post(f'{app}/fax',
                             json={'sender': 'intruder', 'text': 'let me in'},
                             timeout=REQUEST_TIMEOUT)

    assert response.status_code == 401
    # The printer socket is only opened inside print_fax, so if auth is checked
    # first there is nothing to race against here.
    assert printer.jobs == []


def test_fax_posted_over_http_arrives_at_the_printer(app: str, printer: FakePrinter) -> None:
    payload = {
        'sender': 'smoke test',
        'text': 'The quick brown fox jumps over the lazy dog.\n' * 8,
        'ts': '2026-08-01T12:00:00Z',
        'avatar': png_b64((150, 150)),
        'images': [png_b64((200, 120))],
    }

    response = requests.post(f'{app}/fax',
                             json=payload,
                             headers={'Authorization': f'Bearer {TOKEN}'},
                             timeout=REQUEST_TIMEOUT)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body['status'] == 'printed'
    assert body['width'] == PROFILE_WIDTH

    job = escpos_stream.parse(printer.wait_for_job(timeout=REQUEST_TIMEOUT))

    assert job.unparsed == b'', 'unrecognised bytes in the ESC/POS stream'
    assert job.fragments, 'no raster image reached the printer'
    assert len(job.fragments) == math.ceil(body['height'] / FRAGMENT_HEIGHT)

    page = job.image
    assert page is not None
    assert page.width == PROFILE_WIDTH
    assert page.height == body['height'], 'the printed page is not the page we rendered'
    assert job.ink_pixels > 0, 'the printer received a blank page'

    assert job.fed, 'paper was never fed'
    assert job.cut, 'paper was never cut'

    # One fax, one connection: the fax was not printed twice or split in half.
    assert len(printer.jobs) == 1


def test_healthz_still_answers_while_a_print_is_stuck(tmp_path: Path) -> None:
    """A stuck printer must not take the whole process down with it.

    Printing blocks: a TCP connect to something on the far end of somebody's
    wifi. Run that on the event loop and a printer that's simply switched off
    means /healthz stops answering at exactly the moment you want to ask it,
    and the Discord gateway misses heartbeats and gets disconnected.
    """
    stuck_for = 15
    with JammedPrinter() as jammed_printer:
        http_port = free_port()
        log_path = tmp_path / 'bot.log'
        with running_app(jammed_printer.port, http_port, log_path,
                         printer_timeout=stuck_for) as proc:
            base_url = f'http://127.0.0.1:{http_port}'
            wait_until_serving(proc, base_url, log_path)

            def send_fax() -> None:
                try:
                    requests.post(f'{base_url}/fax',
                                  json={'sender': 'stuck', 'text': 'anybody home'},
                                  headers={'Authorization': f'Bearer {TOKEN}'},
                                  timeout=stuck_for + REQUEST_TIMEOUT)
                except requests.RequestException:
                    pass  # This one is expected to fail; the point is elsewhere.

            sender = threading.Thread(target=send_fax, daemon=True)
            sender.start()
            try:
                # Long enough for the request to reach the connect and wedge
                # there, short enough to still be inside the stuck window.
                time.sleep(3)

                started = time.monotonic()
                try:
                    response = requests.get(f'{base_url}/healthz', timeout=5)
                except requests.RequestException as exc:
                    pytest.fail(f'/healthz never answered while a print was '
                                f'stuck, so the print is blocking the event '
                                f'loop: {exc!r}')
                elapsed = time.monotonic() - started

                assert response.status_code == 200
                assert elapsed < 2, (
                    f'/healthz took {elapsed:.1f}s while a print was stuck; '
                    'the print is blocking the event loop')

                # Without this the test passes for the wrong reason: if the
                # print had already finished there was never anything to block
                # on, and /healthz being fast proves nothing.
                assert sender.is_alive(), (
                    'the print completed before /healthz was measured -- this '
                    'test did not exercise a stuck printer at all')
            finally:
                sender.join(timeout=stuck_for + REQUEST_TIMEOUT)
