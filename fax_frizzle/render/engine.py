"""
Image rendering engine for the fax service.
"""
from PIL import Image, ImageDraw, ImageFont


def render_fax(width: int) -> Image.Image:
    """
    Creates a simple "Hello World" image using PIL.

    Args:
        output_path: Path to save the image (optional)

    Returns:
        PIL Image object with "Hello World" text
    """
    # Create a new image with white background
    size = (800, 300)
    img = Image.new('RGB', size, color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Use default font
    font = ImageFont.load_default()

    # Get the text size
    text = "Hello World"
    text_width, text_height = (
        draw.textbbox((0, 0), text, font=font)[2:4]  # For newer PIL versions
    )

    # Calculate position to center the text
    position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)

    # Draw the text in black
    draw.text(position, text, font=font, fill=(0, 0, 0))

    return img
