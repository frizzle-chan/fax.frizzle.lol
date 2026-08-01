"""
Rendering a fax and pushing it at the printer, with no idea where it came from.
"""
import asyncio
import os
from dataclasses import replace
from pathlib import Path

from escpos.escpos import Escpos
from PIL import Image, ImageOps

from fax_frizzle.fax import Fax
from fax_frizzle.render.engine import render_fax

current_dir = Path(os.path.dirname(os.path.abspath(__file__)))

# Attachments are clamped here rather than in each source: how big a picture may
# be on paper is a printing concern, not a transport one.
MAX_ATTACHMENT_SIZE = (512, 512)


class FaxService:
    """
    Renders faxes and prints them, one at a time.

    All sources must share a single instance. The lock is the only thing keeping
    two inputs from interleaving ESC/POS on the same socket, and it can only do
    that if there is one of it.
    """

    def __init__(self, printer: Escpos) -> None:
        self._printer = printer
        self._lock = asyncio.Lock()

    @property
    def width(self) -> int:
        """Printable width of the loaded printer profile, in pixels."""
        return int(self._printer.profile.profile_data["media"]["width"]["pixels"])

    async def print_fax(self, fax: Fax) -> Image.Image:
        """Render `fax`, print it, and return the image that went to the printer."""
        fax = replace(fax, image_attachments=[
            ImageOps.contain(img, MAX_ATTACHMENT_SIZE) for img in fax.image_attachments
        ])
        rendered_fax = render_fax(fax=fax, width=self.width)

        async with self._lock:
            try:
                self._printer.open()
                self._printer.image(rendered_fax)
                self._printer.cut()
            finally:
                self._printer.close()

        return rendered_fax
