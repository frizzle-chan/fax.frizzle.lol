"""
HTTP input source.

This is the adapter the smoke test drives, and it is the shape inbound email
will arrive in: a mail provider's webhook is just a POST. Anything that can
speak JSON can send a fax without knowing Discord exists.

    POST /fax
    Authorization: Bearer $FAX_HTTP_TOKEN
    {
      "sender": "austin",
      "text":   "hello from the internet",
      "ts":     "2026-08-01T12:00:00Z",   # optional, defaults to now
      "avatar": "<base64 png/jpeg>",      # optional
      "images": ["<base64 png/jpeg>"]     # optional
    }

    -> 200 {"status": "printed", "width": 512, "height": 1234}
"""
import asyncio
import base64
import hmac
import json
import logging
from io import BytesIO
from typing import Any, List, Optional

import arrow
from aiohttp import web
from PIL import Image, UnidentifiedImageError

from fax_frizzle.fax import Fax
from fax_frizzle.service import FaxService

# This endpoint makes physical paper come out of a printer on someone's desk,
# so the limits are deliberately mean.
MAX_BODY_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARS = 4000
MAX_IMAGES = 8
# Generous enough for a phone photo, mean enough that a decompression bomb is
# refused before Pillow allocates it.
MAX_IMAGE_PIXELS = 50_000_000

log = logging.getLogger(__name__)


def _bad_request(message: str) -> web.HTTPBadRequest:
    return web.HTTPBadRequest(text=json.dumps({'error': message}),
                              content_type='application/json')


def _decode_image(raw: Any, label: str) -> Image.Image:
    if not isinstance(raw, str):
        raise _bad_request(f'{label} must be a base64 string')
    try:
        # binascii.Error is a subclass of ValueError.
        data = base64.b64decode(raw, validate=True)
    except ValueError:
        raise _bad_request(f'{label} is not valid base64')
    try:
        img = Image.open(BytesIO(data))
        # open() only reads the header, so the dimensions are known before
        # anything is decoded. Pillow's own guard only fires at 2x its
        # threshold; a picture half that size still decodes to gigabytes on a
        # Raspberry Pi.
        width, height = img.size
        if width * height > MAX_IMAGE_PIXELS:
            raise _bad_request(f'{label} is too large: {width}x{height}')
        # Decode now so a truncated or hostile payload fails here as a 400
        # rather than later as a 500 out of the renderer.
        img.load()
    except Image.DecompressionBombError:
        # Raised from open() as well as load(), and it subclasses plain
        # Exception rather than OSError or ValueError, so it needs its own arm
        # or it escapes as a 500.
        raise _bad_request(f'{label} is a decompression bomb')
    except (UnidentifiedImageError, OSError, ValueError):
        raise _bad_request(f'{label} is not a readable image')
    return img


def parse_fax(payload: Any) -> Fax:
    """Build a Fax from a decoded JSON body, or raise a 400."""
    if not isinstance(payload, dict):
        raise _bad_request('body must be a JSON object')

    sender = payload.get('sender')
    if not isinstance(sender, str) or not sender.strip():
        raise _bad_request('sender is required')

    text = payload.get('text', '')
    if not isinstance(text, str):
        raise _bad_request('text must be a string')
    if len(text) > MAX_TEXT_CHARS:
        raise _bad_request(f'text must be at most {MAX_TEXT_CHARS} characters')

    raw_ts = payload.get('ts')
    if raw_ts is None:
        ts = arrow.utcnow().datetime
    else:
        try:
            ts = arrow.get(raw_ts).datetime
        except (arrow.parser.ParserError, ValueError, TypeError):
            raise _bad_request('ts must be an ISO 8601 timestamp')

    avatar: Optional[Image.Image] = None
    if payload.get('avatar') is not None:
        avatar = _decode_image(payload['avatar'], 'avatar')

    # Not `or []`: that would quietly wave through a falsy non-list like 0 or "".
    raw_images = payload.get('images')
    if raw_images is None:
        raw_images = []
    if not isinstance(raw_images, list):
        raise _bad_request('images must be a list')
    if len(raw_images) > MAX_IMAGES:
        raise _bad_request(f'at most {MAX_IMAGES} images per fax')
    images: List[Image.Image] = [
        _decode_image(raw, f'images[{i}]') for i, raw in enumerate(raw_images)
    ]

    return Fax(user_name=sender,
               text=text,
               ts=ts,
               user_avatar=avatar,
               image_attachments=images)


def authorized(header: str, token: str) -> bool:
    """Check an Authorization header against the shared secret."""
    scheme, _, presented = header.partition(' ')
    if scheme.lower() != 'bearer':
        return False
    # Compare as bytes: compare_digest refuses str with non-ASCII in it, so a
    # header like `Bearer tökén` would raise TypeError and come back as a 500
    # with a traceback instead of a 401 -- and a non-ASCII token would break
    # every request, including the valid ones.
    return hmac.compare_digest(presented.encode('utf-8'), token.encode('utf-8'))


def make_app(service: FaxService, token: str) -> web.Application:
    async def healthz(request: web.Request) -> web.Response:
        # Unauthenticated on purpose: it reveals nothing and it is how the smoke
        # test (and any process supervisor) knows the printer pipeline is up.
        return web.json_response({'status': 'ok', 'width': service.width})

    async def post_fax(request: web.Request) -> web.Response:
        if not authorized(request.headers.get('Authorization', ''), token):
            return web.json_response({'error': 'unauthorized'}, status=401)

        try:
            payload = await request.json()
        except ValueError:
            raise _bad_request('body must be valid JSON')

        fax = parse_fax(payload)
        rendered_fax = await service.print_fax(fax)
        log.info('Received fax over HTTP from %s', fax.user_name)
        print(f"Received fax over HTTP from {fax.user_name}", flush=True)
        return web.json_response({
            'status': 'printed',
            'width': rendered_fax.width,
            'height': rendered_fax.height,
        })

    # client_max_size turns an oversized body into a 413 before we allocate it.
    app = web.Application(client_max_size=MAX_BODY_BYTES)
    app.router.add_get('/healthz', healthz)
    app.router.add_post('/fax', post_fax)
    return app


async def run(service: FaxService, token: str, host: str, port: int) -> None:
    """Serve the HTTP fax endpoint until cancelled."""
    runner = web.AppRunner(make_app(service, token))
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"HTTP fax source listening on {host}:{port}", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
