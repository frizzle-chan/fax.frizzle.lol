from dataclasses import dataclass
from datetime import datetime
import re
from typing import List, Optional, Union

from PIL import Image
import arrow
from discord import Attachment, Member, User

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
    