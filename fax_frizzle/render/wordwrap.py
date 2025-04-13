
import re
from typing import List

from PIL import ImageFont


def wordwrap(font: ImageFont.FreeTypeFont, width: int, text: str) -> str:
    raw_lines = text.splitlines()
    out_lines: List[str] = []
    for raw_line in raw_lines:
        if font.getlength(raw_line) <= width:
            out_lines.append(raw_line)
            continue

        current_line: List[str] = []
        token: str
        for token in re.split(r'(\s+)', raw_line):
            current_line.append(token)
            # Handle whitespace token
            if not token.strip():
                continue
            # Check if the line fits in the width
            if font.getlength(''.join(current_line)) <= width:
                continue
            # If it doesn't fit, add the current line to the lines list and start a new line
            current_line.pop()
            out_lines.append(''.join(current_line))
            current_line = [token]

        if current_line:
            out_lines.append(''.join(current_line))
    return '\n'.join(out_lines)
