"""
Image rendering engine for the fax service.
"""
from typing import Union
from PIL import Image, ImageDraw, ImageFont

from fax_frizzle.fax import Fax

def render_fax(fax: Fax, width: int) -> Image.Image:
    """
    Creates a simple "Hello World" image using PIL.

    Args:
        output_path: Path to save the image (optional)

    Returns:
        PIL Image object with "Hello World" text
    """
    # Create a new image with white background
    size = (width, width)
    img = Image.new('RGB', size, color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    gr = 1.618  # Golden ratio

    h_margin = int(width // gr // (2*3))
    v_margin = int(width // gr // (2*3))
    scroll = 0

    # Use default font
    font = ImageFont.load_default()

    def draw_centered_text(text: str, font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont], **kwargs) -> None:
        text_width, text_height = (
            draw.textbbox((0, 0), text, font=font)[2:4]
        )
        defaults = {
            "fill": (0, 0, 0),
        }
        # Merge defaults with any kwargs provided
        final_kwargs = {**defaults, **kwargs}
        draw.text(
            ((width - text_width) / 2, scroll),
            text,
            **final_kwargs
        )

    scroll += v_margin
    fax.user_avatar.thumbnail((150, 150))
    img.paste(fax.user_avatar, (int(width // 2) - int(fax.user_avatar.width // 2), scroll))
    scroll += fax.user_avatar.height
    scroll += int(v_margin // 2)

    draw_centered_text(font=font, text=fax.user_name)

    return img
