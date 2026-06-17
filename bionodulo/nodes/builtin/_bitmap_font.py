"""Tiny 5x7 bitmap font for labelling hand-rolled PNG charts.

The chart renderers in ``visualization.py`` rasterise PNGs without any drawing
library (no matplotlib/PIL available), so they previously produced charts with
no title or axis labels. This module provides a dependency-free way to blit
short strings (titles, axis names, numeric ticks, category labels) into an
RGB ``bytearray`` pixel buffer.

Glyphs are 5 wide x 7 tall. Lowercase letters reuse the uppercase glyphs.
"""

from __future__ import annotations

# Each glyph is 7 rows of 5 columns; "#" = ink, " " = transparent.
_GLYPHS: dict[str, tuple[str, ...]] = {
    " ": ("     ", "     ", "     ", "     ", "     ", "     ", "     "),
    "0": (" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "),
    "1": ("  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "),
    "2": (" ### ", "#   #", "    #", "  ## ", " #   ", "#    ", "#####"),
    "3": ("#####", "   # ", "  #  ", "   # ", "    #", "#   #", " ### "),
    "4": ("   ##", "  # #", " #  #", "#   #", "#####", "    #", "    #"),
    "5": ("#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "),
    "6": ("  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "),
    "7": ("#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "),
    "8": (" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "),
    "9": (" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "),
    "A": (" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "B": ("#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "),
    "C": (" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "),
    "D": ("###  ", "#  # ", "#   #", "#   #", "#   #", "#  # ", "###  "),
    "E": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"),
    "F": ("#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "),
    "G": (" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ### "),
    "H": ("#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"),
    "I": (" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "),
    "J": ("  ###", "   # ", "   # ", "   # ", "#  # ", "#  # ", " ##  "),
    "K": ("#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"),
    "M": ("#   #", "## ##", "# # #", "#   #", "#   #", "#   #", "#   #"),
    "N": ("#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"),
    "O": (" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "P": ("#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "),
    "Q": (" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"),
    "R": ("#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"),
    "S": (" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "),
    "T": ("#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "),
    "U": ("#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "),
    "V": ("#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "),
    "W": ("#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"),
    "X": ("#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"),
    "Y": ("#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "),
    "Z": ("#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"),
    ".": ("     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "),
    ",": ("     ", "     ", "     ", "     ", " ##  ", " ##  ", " #   "),
    ":": ("     ", " ##  ", " ##  ", "     ", " ##  ", " ##  ", "     "),
    ";": ("     ", " ##  ", " ##  ", "     ", " ##  ", " ##  ", " #   "),
    "-": ("     ", "     ", "     ", "#####", "     ", "     ", "     "),
    "_": ("     ", "     ", "     ", "     ", "     ", "     ", "#####"),
    "+": ("     ", "  #  ", "  #  ", "#####", "  #  ", "  #  ", "     "),
    "/": ("    #", "    #", "   # ", "  #  ", " #   ", "#    ", "#    "),
    "%": ("##  #", "##  #", "   # ", "  #  ", " #   ", "#  ##", "#  ##"),
    "(": ("  #  ", " #   ", "#    ", "#    ", "#    ", " #   ", "  #  "),
    ")": ("  #  ", "   # ", "    #", "    #", "    #", "   # ", "  #  "),
    "=": ("     ", "     ", "#####", "     ", "#####", "     ", "     "),
    "#": (" # # ", " # # ", "#####", " # # ", "#####", " # # ", " # # "),
    "?": (" ### ", "#   #", "    #", "  ## ", "  #  ", "     ", "  #  "),
}

GLYPH_W = 5
GLYPH_H = 7
_UNKNOWN = _GLYPHS["?"]


def char_width(scale: int) -> int:
    """Advance width of one character cell (glyph + 1 column spacing)."""
    return (GLYPH_W + 1) * scale


def text_width(text: str, scale: int = 1) -> int:
    return len(text) * char_width(scale)


def draw_text(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    text: str,
    color: tuple[int, int, int],
    scale: int = 1,
) -> int:
    """Blit *text* into an RGB pixel buffer with top-left at (x, y).

    Returns the x coordinate just past the drawn text. Out-of-bounds pixels are
    clipped silently.
    """
    scale = max(1, int(scale))
    cursor = x
    for ch in text:
        glyph = _GLYPHS.get(ch) or _GLYPHS.get(ch.upper()) or _UNKNOWN
        for row in range(GLYPH_H):
            pattern = glyph[row]
            for col in range(GLYPH_W):
                if pattern[col] != "#":
                    continue
                for dy in range(scale):
                    for dx in range(scale):
                        px = cursor + col * scale + dx
                        py = y + row * scale + dy
                        if 0 <= px < width and 0 <= py < height:
                            offset = (py * width + px) * 3
                            pixels[offset] = color[0]
                            pixels[offset + 1] = color[1]
                            pixels[offset + 2] = color[2]
        cursor += char_width(scale)
    return cursor


def draw_text_centered(
    pixels: bytearray,
    width: int,
    height: int,
    center_x: int,
    y: int,
    text: str,
    color: tuple[int, int, int],
    scale: int = 1,
) -> None:
    start_x = int(center_x - text_width(text, scale) / 2)
    draw_text(pixels, width, height, start_x, y, text, color, scale)


def fit_scale(text: str, max_width: int, preferred: int = 2) -> int:
    """Largest scale (down to 1) whose rendered width fits *max_width*."""
    for scale in range(preferred, 0, -1):
        if text_width(text, scale) <= max_width:
            return scale
    return 1
