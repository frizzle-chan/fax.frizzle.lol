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
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Iterator

import pytest
import requests
from PIL import Image

from smoke_test import escpos_stream
from smoke_test.fake_printer import FakePrinter, free_port

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
def running_app(printer_port: int, http_port: int, log_path: Path) -> Iterator[subprocess.Popen]:
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
        'PYTHONUNBUFFERED': '1',
    }
    # Straight to a file rather than a PIPE: nobody is draining a pipe while we
    # poll for readiness, and a chatty failure would fill the buffer and wedge
    # the child (and then the CI job) forever.
    with log_path.open('wb') as log:
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

    # pytest swallows this unless the test failed, in which case it's the only
    # way to find out what the child thought it was doing.
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
