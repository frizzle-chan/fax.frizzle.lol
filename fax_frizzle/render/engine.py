"""
Image rendering engine for the fax service.
"""
import math
import sys
from datetime import datetime
from typing import List

import arrow
from PIL import Image, ImageDraw, ImageFont

from fax_frizzle.fax import Fax
from fax_frizzle.render.wordwrap import wordwrap

_fsize = 16
font_meta = ImageFont.truetype('unifontex.ttf', _fsize // 2)
font_body = ImageFont.truetype('unifontex.ttf', _fsize)
font_title = ImageFont.truetype('unifontex.ttf', _fsize * 2)

gr = 1.618  # Golden ratio


def make_avatar_tile(width: int, avatar: Image.Image) -> Image.Image:
    avatar.thumbnail((150, 150))
    img = Image.new('RGB', (width, avatar.height), color=(255, 255, 255))
    img.paste(avatar, (int(width // 2) - int(avatar.width // 2), 0))
    return img


def centered_text_tile(width: int, text: str, font: ImageFont.FreeTypeFont, **kwargs) -> Image.Image:
    defaults: dict = dict()
    # Merge defaults with any kwargs provided
    final_kwargs = {**defaults, **kwargs}
    tmp = Image.new('RGB', (0, 0), color=(255, 255, 255))
    tmp_draw = ImageDraw.Draw(tmp)
    t_left, t_top, t_right, t_bottom = tmp_draw.textbbox((0, 0), text, font=font, **final_kwargs)
    t_height = math.ceil(t_bottom - t_top)
    t_width = math.ceil(t_right - t_left)
    padding = int(t_height // 2)
    img = Image.new('RGB', (width, t_height + padding * 2), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    final_kwargs['fill'] = (0, 0, 0)
    draw.text(
        ((width - t_width) / 2, padding),
        text,
        font=font,
        **final_kwargs
    )
    return img


def body_text_tile(width: int, text: str, font: ImageFont.FreeTypeFont, **kwargs) -> Image.Image:
    padding = int(width // gr // (2 * 16))
    text = wordwrap(font, width, text)
    defaults: dict = dict()
    # Merge defaults with any kwargs provided
    final_kwargs = {**defaults, **kwargs}
    tmp = Image.new('RGB', (0, 0), color=(255, 255, 255))
    tmp_draw = ImageDraw.Draw(tmp)
    t_left, t_top, t_right, t_bottom = tmp_draw.multiline_textbbox((0, 0), text, font=font, **final_kwargs)
    t_height = math.ceil(t_bottom - t_top)
    img = Image.new('RGB', (width, t_height + padding * 2), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    final_kwargs['fill'] = (0, 0, 0)
    draw.text(
        (0, padding),
        text,
        font=font,
        **final_kwargs
    )
    return img


def render_fax(fax: Fax, width: int) -> Image.Image:
    v_padding = int(width // (gr * 3))

    if len(fax.text) > 54 or "\n" in fax.text:
        body = body_text_tile(width, fax.text, font_body)
    else:
        body = centered_text_tile(width, fax.text, font_body)

    tiles: List[int | Image.Image] = [
        v_padding,
        make_avatar_tile(width, fax.user_avatar),
        int(v_padding // 10),
        centered_text_tile(width, fax.user_name, font_title),
        centered_text_tile(width, fax.human_ts, font_body),
        int(v_padding // 4),
        body,
    ]

    for img in fax.image_attachments:
        tiles.append(int(v_padding // 4))
        img_copy = img.copy()
        if img_copy.size[0] > width:
            img_copy.thumbnail((width, sys.maxsize))
        img_attachment_tile = Image.new('RGB', (width, img_copy.height), color=(255, 255, 255))
        img_attachment_tile.paste(img_copy, ((width // 2) - (img_copy.width // 2), 0), mask=img_copy if img_copy.mode == 'RGBA' else None)

        tiles.append(img_attachment_tile)
    tiles.append(v_padding)

    final_height = sum(tile.height if isinstance(tile, Image.Image) else tile for tile in tiles)
    img = Image.new('RGB', (width, final_height), color=(255, 255, 255))
    scroll = 0
    for tile in tiles:
        if isinstance(tile, Image.Image):
            img.paste(tile, (0, scroll))
            scroll += tile.height
            continue
        scroll += tile

    return img


def sent_to_printer_badge(ts: datetime) -> Image.Image:
    w = 275
    stp_tile = centered_text_tile(w, "Sent to printer", font_body)
    ts_tile = centered_text_tile(w, arrow.get(ts).format(arrow.FORMAT_RSS), font_body)
    img = Image.new('RGB', (w, stp_tile.height + ts_tile.height + 8), color=(255, 255, 255))
    img.paste(stp_tile, (0, 0))
    img.paste(ts_tile, (0, stp_tile.height))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, w - 1, img.height - 1), outline=(0, 0, 0), width=1)

    return img
