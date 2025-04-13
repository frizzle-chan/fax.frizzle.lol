import re
from dataclasses import dataclass
from datetime import datetime
from typing import List

import arrow
from PIL import Image

# ASCII only
_printable_pattern = re.compile(r'[^\x00-\x7F]+', flags=re.UNICODE)


@dataclass
class Fax:
    """
    A fax object that contains the fax number, the text to be sent, and the attachments.
    """
    user_name: str
    user_avatar: Image.Image
    text: str
    ts: datetime
    image_attachments: List[Image.Image]

    def __post_init__(self):
        pass

    @property
    def human_ts(self) -> str:
        return arrow.get(self.ts)\
            .to('local')\
            .format('ddd, MMM Do, YYYY h:mmA')

    @property
    def safe_text(self) -> str:
        """
        Return the text with non-ASCII characters replaced with underscores.
        """
        return _printable_pattern.sub('_', self.text)
