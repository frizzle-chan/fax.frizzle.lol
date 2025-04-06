"""
Image rendering engine for the fax service.
"""
import math
from typing import List, Union
from PIL import Image, ImageDraw, ImageFont

from fax_frizzle.fax import Fax

font_body = ImageFont.truetype('unifontex.ttf', 16)

def make_avatar_tile(width: int, avatar: Image.Image) -> Image.Image:
    avatar.thumbnail((150, 150))
    img = Image.new('RGB', (width, avatar.height), color=(255, 255, 255))
    img.paste(avatar, (int(width // 2) - int(avatar.width // 2), 0))
    return img

def centered_text_tile(width: int, text: str, font: ImageFont.FreeTypeFont, **kwargs) -> Image.Image:
    defaults = dict()
    # Merge defaults with any kwargs provided
    final_kwargs = {**defaults, **kwargs}
    tmp = Image.new('RGB', (0, 0), color=(255, 255, 255))
    tmp_draw = ImageDraw.Draw(tmp)
    t_left, t_top, t_right, t_bottom = tmp_draw.textbbox((0, 0), text, font=font, **final_kwargs)
    t_height = math.ceil(t_bottom - t_top)
    t_width = math.ceil(t_right - t_left)
    padding = int(t_height // 2)
    img = Image.new('RGB', (width, t_height + padding*2), color=(255, 0, 255))
    draw = ImageDraw.Draw(img)
    final_kwargs['fill'] = (0, 0, 0)
    draw.text(
        ((width - t_width) / 2, padding),
        text,
        font=font,
        **final_kwargs
    )
    return img


def render_fax(fax: Fax, width: int) -> Image.Image:
    gr = 1.618  # Golden ratio
    h_margin = int(width // gr // (2*3))
    v_margin = int(width // gr // (2*3))

    tiles: List[int | Image.Image] = [
        v_margin,
        make_avatar_tile(width, fax.user_avatar),
        int(v_margin // 2),
        centered_text_tile(width, fax.user_name, font_body),
        centered_text_tile(width, fax.text, font_body),
    ]
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
