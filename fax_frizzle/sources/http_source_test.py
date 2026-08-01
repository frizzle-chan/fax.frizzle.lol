import base64
import json
from io import BytesIO

import pytest
from aiohttp import web
from PIL import Image

from fax_frizzle.sources import http_source
from fax_frizzle.sources.http_source import (MAX_IMAGES, MAX_TEXT_CHARS,
                                             authorized, parse_fax)


def png_b64(size=(16, 16)) -> str:
    stream = BytesIO()
    Image.new('RGB', size, (0, 0, 0)).save(stream, 'PNG')
    return base64.b64encode(stream.getvalue()).decode('ascii')


def test_parses_a_minimal_payload():
    fax = parse_fax({'sender': 'austin', 'text': 'hi'})

    assert fax.user_name == 'austin'
    assert fax.text == 'hi'
    assert fax.user_avatar is None
    assert fax.image_attachments == []
    # No ts given, so it defaults to now rather than blowing up.
    assert fax.ts is not None


def test_parses_a_full_payload():
    fax = parse_fax({
        'sender': 'austin',
        'text': 'hi',
        'ts': '2026-08-01T12:00:00Z',
        'avatar': png_b64((150, 150)),
        'images': [png_b64(), png_b64()],
    })

    assert fax.ts.isoformat() == '2026-08-01T12:00:00+00:00'
    assert fax.user_avatar is not None
    assert fax.user_avatar.size == (150, 150)
    assert len(fax.image_attachments) == 2


@pytest.mark.parametrize('payload,reason', [
    ('not a dict', 'body must be a JSON object'),
    ({}, 'sender is required'),
    ({'sender': '   '}, 'sender is required'),
    ({'sender': 'a', 'text': 7}, 'text must be a string'),
    ({'sender': 'a', 'text': 'x' * (MAX_TEXT_CHARS + 1)}, 'at most'),
    ({'sender': 'a', 'ts': 'yesterday-ish'}, 'ISO 8601'),
    ({'sender': 'a', 'avatar': 'not base64!!'}, 'not valid base64'),
    ({'sender': 'a', 'avatar': base64.b64encode(b'nope').decode()}, 'not a readable image'),
    ({'sender': 'a', 'images': 'nope'}, 'images must be a list'),
    ({'sender': 'a', 'images': [png_b64()] * (MAX_IMAGES + 1)}, 'at most'),
    # Falsy non-lists have to be rejected too, not quietly treated as absent.
    ({'sender': 'a', 'images': 0}, 'images must be a list'),
    ({'sender': 'a', 'images': False}, 'images must be a list'),
    ({'sender': 'a', 'images': ''}, 'images must be a list'),
])
def test_rejects_bad_payloads(payload, reason):
    with pytest.raises(web.HTTPBadRequest) as excinfo:
        parse_fax(payload)

    # The body has to be JSON an actual client can parse, not a Python repr.
    assert reason in json.loads(excinfo.value.text)['error']


def test_rejects_a_decompression_bomb(monkeypatch):
    # Pillow raises DecompressionBombError past 2x its own threshold -- from
    # open(), not load(), and it subclasses plain Exception. Without a dedicated
    # except arm this escapes as a 500.
    monkeypatch.setattr(Image, 'MAX_IMAGE_PIXELS', 8)

    with pytest.raises(web.HTTPBadRequest) as excinfo:
        parse_fax({'sender': 'a', 'images': [png_b64((64, 64))]})

    assert 'decompression bomb' in json.loads(excinfo.value.text)['error']


def test_rejects_an_image_too_big_to_decode(monkeypatch):
    # The guard reads the header, so a small image with the cap dropped under it
    # exercises the same path a real bomb would, without building one.
    monkeypatch.setattr(http_source, 'MAX_IMAGE_PIXELS', 10)

    with pytest.raises(web.HTTPBadRequest) as excinfo:
        parse_fax({'sender': 'a', 'images': [png_b64((64, 64))]})

    assert 'too large' in json.loads(excinfo.value.text)['error']


@pytest.mark.parametrize('header,token,expected', [
    ('Bearer hunter2', 'hunter2', True),
    ('bearer hunter2', 'hunter2', True),
    ('Bearer wrong', 'hunter2', False),
    ('Bearer', 'hunter2', False),
    ('', 'hunter2', False),
    ('Basic hunter2', 'hunter2', False),
    ('hunter2', 'hunter2', False),
    # compare_digest refuses str with non-ASCII in it. These must come back
    # False, not blow up into a 500 with a traceback.
    ('Bearer tökén', 'hunter2', False),
    ('Bearer hunter2', 'tökén', False),
    ('Bearer tökén', 'tökén', True),
])
def test_authorized(header, token, expected):
    assert authorized(header, token) is expected
