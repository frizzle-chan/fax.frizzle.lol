import base64
import json
from io import BytesIO

import pytest
from aiohttp import web
from PIL import Image

from fax_frizzle.sources.http_source import (MAX_IMAGES, MAX_TEXT_CHARS,
                                             parse_fax)


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
])
def test_rejects_bad_payloads(payload, reason):
    with pytest.raises(web.HTTPBadRequest) as excinfo:
        parse_fax(payload)

    # The body has to be JSON an actual client can parse, not a Python repr.
    assert reason in json.loads(excinfo.value.text)['error']
