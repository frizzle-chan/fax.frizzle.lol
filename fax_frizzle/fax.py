import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

import arrow
from PIL import Image

# ASCII only
_printable_pattern = re.compile(r'[^\x00-\x7F]+', flags=re.UNICODE)


@dataclass
class Fax:
    """
    A fax object that contains the fax number, the text to be sent, and the attachments.

    Deliberately knows nothing about where it came from -- Discord, HTTP, and
    (soon) email all build one of these and hand it to the FaxService.
    """
    user_name: str
    text: str
    ts: datetime
    # Optional so a source with no avatar doesn't have to reach for the
    # placeholder image itself; the renderer supplies the fallback.
    user_avatar: Optional[Image.Image] = None
    image_attachments: List[Image.Image] = field(default_factory=list)

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
