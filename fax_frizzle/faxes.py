import asyncio
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Union

import requests
from cachetools import TTLCache, cached
from discord import Attachment, Member, User
from escpos.escpos import Escpos
from PIL import Image, ImageOps

from fax_frizzle.fax import Fax
from fax_frizzle.render.engine import render_fax, sent_to_printer_badge

lock = asyncio.Lock()

# Get the directory where the current file is located
current_dir = Path(os.path.dirname(os.path.abspath(__file__)))


@cached(cache=TTLCache(maxsize=10, ttl=60 * 60 * 24))
def download_avatar(avatar_url: str) -> Image.Image:
    """
    Download an avatar image from a URL and save it as a PIL Image object.

    I expect this to be fairly sleepy and mostly just wanna guard against the
    same user spamming over and over. So keeping 10 avatars in memory for 24
    hours should be okay.
    """

    response = requests.get(avatar_url)
    response.raise_for_status()
    img = Image.open(BytesIO(response.content))
    img.thumbnail((150, 150))
    return img


def download_attachment_image(url: str) -> Image.Image:
    response = requests.get(url)
    response.raise_for_status()
    img = Image.open(BytesIO(response.content))
    return ImageOps.contain(img, (512, 512))


async def send_fax(printer: Escpos,
                   user: Union[User, Member],
                   text: str,
                   ts: datetime,
                   attachments: Optional[List[Attachment]] = None) -> Image.Image:
    if user.avatar:
        avatar = download_avatar(user.avatar.url)
        avatar = avatar.resize((150, 150))
    else:
        avatar = Image.open(current_dir / "img/question.png")

    image_attachments = []
    if attachments:
        for attachment in attachments:
            if attachment.content_type == 'image/png' or \
                    attachment.content_type == 'image/jpeg':
                image_attachments.append(download_attachment_image(attachment.url))

    fax = Fax(user_name=user.name, user_avatar=avatar, text=text, ts=ts, image_attachments=image_attachments)
    rendered_fax = render_fax(fax=fax, width=printer.profile.profile_data["media"]["width"]["pixels"])

    async with lock:
        try:
            printer.open()
            printer.image(rendered_fax)
            printer.cut()
        finally:
            printer.close()

    return rendered_fax


def convert_fax_to_preview(fax_img: Image.Image, ts: datetime) -> Image.Image:
    im = fax_img.copy()
    # Pure black and white
    im = im.convert("1")
    # sticker = Image.open(current_dir / "img/print-preview.png")
    # sticker.thumbnail((fax_img.width, fax_img.height))
    preview_img = Image.new("RGB", (fax_img.width + 16, fax_img.height), (255, 255, 255))
    preview_img.paste(im, (8, 0))
    # preview_img.paste(sticker, ((preview_img.width // 2) - (sticker.width // 2), (preview_img.height // 2) - (sticker.height // 2)), sticker)
    stp = sent_to_printer_badge(ts)
    preview_img.paste(stp, (preview_img.width - stp.width - 8, 8))

    return preview_img
