import re
from io import BytesIO

import arrow
import requests
from cachetools import TTLCache, cached
from discord import Message
from escpos.escpos import Escpos
from PIL import Image, ImageOps


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


# ASCII only
_printable_pattern = re.compile(r'[^\x00-\x7F]+', flags=re.UNICODE)


def _safe(text: str) -> str:
    return _printable_pattern.sub('_', text)


def send_fax(printer: Escpos, message: Message) -> None:
    human_date = arrow.get(message.created_at)\
        .to('local')\
        .format('ddd, MMM Do, YYYY h:mmA')

    msg = _safe(message.content)
    msg = re.sub(r'^\$fax ?', '', msg, flags=re.IGNORECASE)

    printer.textln()
    if message.author.avatar:
        avatar = download_avatar(message.author.avatar.url)
        avatar = avatar.resize((150, 150))
        printer.image(avatar, center=True)
        printer.textln()
    printer.set(bold=True, font='b', align='center')
    printer.textln(_safe(message.author.name))
    printer.set(bold=False)
    printer.textln(human_date)
    printer.set(bold=False, font='a', align='left')
    printer.textln()
    printer.textln(msg)
    printer.textln()
    for attachment in message.attachments:
        if attachment.content_type == 'image/png' or \
                attachment.content_type == 'image/jpeg':
            image = download_attachment_image(attachment.url)
            printer.image(image, center=True)
            printer.textln()
    printer.cut()
