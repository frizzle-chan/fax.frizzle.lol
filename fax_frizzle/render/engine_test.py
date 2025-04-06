from io import BytesIO
from PIL import Image
import arrow

from fax_frizzle.fax import Fax
from fax_frizzle.render.engine import render_fax
import os
from pathlib import Path

# Get the directory where the current file is located
current_dir = Path(os.path.dirname(os.path.abspath(__file__)))

def test_render_fax(image_regression):
    # Create the image
    img = render_fax(width=512,
                      fax=Fax(user_name="Test User",
                              user_avatar=Image.open(current_dir / "../img/question.png"),
                              text="Hello World 😊 👀 😂 🌚 日本語",
                              ts=arrow.get('2013-05-11T21:23:58.970460+07:00').datetime,
                              image_attachments=[]))
    stream = BytesIO()
    img.save(stream, "PNG")
    image_regression.check(stream.getvalue())
