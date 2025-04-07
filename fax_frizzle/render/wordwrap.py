
import re
from collections import deque
from typing import List

from PIL import ImageFont


def wordwrap(font: ImageFont.FreeTypeFont, width: int, text: str) -> str:
    tokens = deque(re.split(r'(\s+)', text))
    lines = []
    current_line: List[str] = []
    while tokens:
        token = tokens.popleft()
        # Handle whitespace token
        if not token.strip():
            for ws in re.split(r'(\n)', token):
                if ws == "\n":
                    lines.append(''.join(current_line))
                    current_line = []
                elif ws:
                    current_line.append(ws)
            continue
        # Check if the line fits in the width
        if font.getlength(''.join(current_line + [token])) <= width:
            current_line.append(token)
            continue
        # If it doesn't fit, add the current line to the lines list and start a new line
        lines.append(''.join(current_line))
        current_line = [token]
    return '\n'.join(lines)
