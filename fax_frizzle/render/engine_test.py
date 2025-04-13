import os
from io import BytesIO
from pathlib import Path

import arrow
from PIL import Image

from fax_frizzle.fax import Fax
from fax_frizzle.faxes import convert_fax_to_preview
from fax_frizzle.render.engine import render_fax

# Get the directory where the current file is located
current_dir = Path(os.path.dirname(os.path.abspath(__file__)))


def test_render_simple_fax(image_regression):
    # Create the image
    img = render_fax(width=512,
                     fax=Fax(user_name="Test User",
                             user_avatar=Image.open(current_dir / "../img/question.png"),
                             text="Hello World 😊 👀 😂 🌚 日本語",
                             ts=arrow.get('2013-05-11T21:23:58.970460+07:00').datetime,
                             image_attachments=[
                                 Image.open(current_dir / "../img/printed_lg.png"),
                                 Image.open(current_dir / "../img/printed.png"),
                                 Image.open(current_dir / "engine_test/IMG_6532.jpg"),
                             ]))
    stream = BytesIO()
    img.save(stream, "PNG")
    image_regression.check(stream.getvalue())


def test_render_simple_fax_preview(image_regression):
    # Create the image
    img = render_fax(width=512,
                     fax=Fax(user_name="Test User",
                             user_avatar=Image.open(current_dir / "../img/question.png"),
                             text="Hello World 😊 👀 😂 🌚 日本語",
                             ts=arrow.get('2013-05-11T21:23:58.970460+07:00').datetime,
                             image_attachments=[
                                 Image.open(current_dir / "../img/printed_lg.png"),
                                 Image.open(current_dir / "../img/printed.png"),
                                 Image.open(current_dir / "engine_test/IMG_6532.jpg"),
                             ]))
    img = convert_fax_to_preview(img, arrow.get('2013-05-11T21:23:58.970460+07:00').datetime)
    stream = BytesIO()
    img.save(stream, "PNG")
    image_regression.check(stream.getvalue())


def test_render_multiline_fax(image_regression):
    # Create the image
    img = render_fax(width=512,
                     fax=Fax(user_name="frizzle✨",
                             user_avatar=Image.open(current_dir / "../img/question.png"),
                             text="""This is a test of the multiline fax rendering.
It should be able to handle multiple lines of text and render them correctly on the image.

This is the second paragraph of the test. It should also be rendered correctly.

IT    SHOULD  BE    ABLE    TO    HANDLE    SPACES    AND                                      TABS    CORRECTLY.

function main() {
    console.log("Hello, World!");
}

def main():
    print("Hello, World!")

This is the third paragraph of the test. It should be rendered correctly as well.
This is the fourth paragraph of the test. It should be rendered correctly as well.
""",
                             ts=arrow.get('2013-05-11T21:23:58.970460+07:00').datetime,
                             image_attachments=[]))
    stream = BytesIO()
    img.save(stream, "PNG")
    image_regression.check(stream.getvalue())
