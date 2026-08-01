"""
Just enough of an ESC/POS reader to prove a fax actually got printed.

python-escpos sends our faxes as `GS v 0` raster bit images, and splits anything
taller than 960px into several of them -- a real fax is well over that -- so
"did an image arrive" means finding every fragment and stacking them back up.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from PIL import Image

RASTER = b'\x1dv0'      # GS v 0, raster bit image
CUT = b'\x1dV'          # GS V m, paper cut
FEED = b'\x1bd'         # ESC d n, print and feed n lines
INIT = b'\x1b@'         # ESC @, initialise


@dataclass
class PrintJob:
    fragments: List[Image.Image] = field(default_factory=list)
    cut: bool = False
    fed: bool = False
    initialised: bool = False
    # Bytes we couldn't account for. Should be empty; if it isn't, either the
    # stream was truncated or something started emitting commands we don't know.
    unparsed: bytes = b''

    @property
    def image(self) -> Optional[Image.Image]:
        """The fragments stacked back into the page that was printed.

        Black pixels are ink, matching what render_fax produced.
        """
        if not self.fragments:
            return None
        width = max(f.width for f in self.fragments)
        height = sum(f.height for f in self.fragments)
        page = Image.new('1', (width, height), 1)
        top = 0
        for fragment in self.fragments:
            page.paste(fragment, (0, top))
            top += fragment.height
        return page

    @property
    def ink_pixels(self) -> int:
        page = self.image
        if page is None:
            return 0
        # Mode "1" histograms only ever have counts at 0 (black) and 255 (white).
        return page.histogram()[0]


def parse(data: bytes) -> PrintJob:
    """Read a captured ESC/POS byte stream into a PrintJob."""
    job = PrintJob()
    unparsed = bytearray()
    i = 0

    while i < len(data):
        if data.startswith(RASTER, i):
            header = i + len(RASTER)
            # density, then width in BYTES and height in ROWS, each 2 bytes LE.
            width_bytes = int.from_bytes(data[header + 1:header + 3], 'little')
            height = int.from_bytes(data[header + 3:header + 5], 'little')
            start = header + 5
            end = start + width_bytes * height
            raster = data[start:end]
            if len(raster) < width_bytes * height:
                unparsed.extend(data[i:])
                break
            # 1 bit per pixel, rows padded out to the byte -- which is why the
            # header counts bytes and this has to multiply by 8 to get pixels.
            fragment = Image.frombytes('1', (width_bytes * 8, height), bytes(raster))
            # escpos inverts before sending (a set bit is ink), so invert back to
            # get an image that looks like the fax.
            job.fragments.append(fragment.point(lambda v: 0 if v else 255, mode='1'))
            i = end
        elif data.startswith(CUT, i):
            job.cut = True
            i += len(CUT) + 1
        elif data.startswith(FEED, i):
            job.fed = True
            i += len(FEED) + 1
        elif data.startswith(INIT, i):
            job.initialised = True
            i += len(INIT)
        else:
            unparsed.append(data[i])
            i += 1

    job.unparsed = bytes(unparsed)
    return job
