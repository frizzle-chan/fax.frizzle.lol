from io import BytesIO
from fax_frizzle.render.engine import render_fax

def test_render_fax(image_regression):
    # Create the image
    img = render_fax()
    stream = BytesIO()
    img.save(stream, "PNG")
    image_regression.check(stream.getvalue())
