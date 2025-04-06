import asyncio
from datetime import datetime
from io import BytesIO
from typing import List, Optional, Union

import requests
from cachetools import TTLCache, cached
from discord import Attachment, Member, User
from escpos.escpos import Escpos
from PIL import Image, ImageOps

from fax_frizzle.fax import Fax

lock = asyncio.Lock()


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
                   attachments: Optional[List[Attachment]] = None) -> None:
    if user.avatar:
        avatar = download_avatar(user.avatar.url)
        avatar = avatar.resize((150, 150))
    else:
        avatar = Image.open("img/question.png")

    image_attachments = []
    if attachments:
        for attachment in attachments:
            if attachment.content_type == 'image/png' or \
                    attachment.content_type == 'image/jpeg':
                image_attachments.append(download_attachment_image(attachment.url))
    fax = Fax(user_name=user.name, user_avatar=avatar, text=text, ts=ts, image_attachments=image_attachments)

    async with lock:
        try:
            printer.open()
            printer.textln()
            if user.avatar:
                printer.image(fax.user_avatar, center=True)
                printer.textln()
            printer.set(bold=True, font='b', align='center')
            printer.textln(fax.user_name)
            printer.set(bold=False)
            printer.textln(fax.human_ts)
            printer.set(bold=False, font='a', align='left')
            printer.textln()
            printer.textln(fax.text)
            printer.textln()
            for attachment in fax.image_attachments:
                printer.image(attachment, center=True)
                printer.textln()
            printer.cut()
        finally:
            printer.close()
