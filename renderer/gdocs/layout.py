"""Tab computation for position/project rows (FR-13) from Roboto font metrics."""

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont

from renderer.gdocs.pdfcheck import MIN_GAP  # the gap the PDF check requires

# Roboto 2.138 static TTFs (the version Google Docs renders as "Roboto"),
# pinned by tag and verified by sha256. Cached under target/gdocs/fonts/.
_BASE = "https://raw.githubusercontent.com/googlefonts/roboto-2/v2.138/src/hinted/"
FONTS = {
    False: ("Roboto-Regular.ttf", _BASE + "Roboto-Regular.ttf",
            "56a45233d29f11b4dfb86d248e921939d115778f87325e7ae8cc108383d6664d"),
    True: ("Roboto-Bold.ttf", _BASE + "Roboto-Bold.ttf",
           "61f89f8db49261c2f6106e8dccc35df7b2f7ed909020db40a3fc905e95f99334"),
}
FONT_DIR = Path(__file__).resolve().parents[2] / "target" / "gdocs" / "fonts"

# Template tab stops in pt, measured from the left margin.
LEFT_STOPS = (36, 72, 108)
CENTER_STOP = 261
RIGHT_STOP = 553


@dataclass(frozen=True)
class Run:
    text: str
    size: float = 10
    bold: bool = False


def fetch_font(bold, font_dir=FONT_DIR):
    """Return the path of the pinned font file, downloading it once and
    verifying its sha256 (also on cache hits)."""
    name, url, sha256 = FONTS[bold]
    path = Path(font_dir) / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as response:
            path.write_bytes(response.read())
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        path.unlink()
        raise RuntimeError(f"A(z) {name} sha256 ellenőrzése sikertelen, a fájl törölve.")
    return path


_font_cache = {}


def roboto_width(text, size, bold):
    """Advance width of `text` in pt (no kerning), from Roboto metrics."""
    if bold not in _font_cache:
        font = TTFont(fetch_font(bold))
        _font_cache[bold] = (font.getBestCmap(), font["hmtx"], font["head"].unitsPerEm)
    cmap, hmtx, upem = _font_cache[bold]
    total = sum(hmtx[cmap.get(ord(c), ".notdef")][0] for c in text)
    return total * size / upem


def runs_width(runs, width_fn=roboto_width):
    return sum(width_fn(r.text, r.size, r.bold) for r in runs)


def _place(x, width, target, stops, space=0.0):
    """Place a part of `width` after position x using tabs aimed at stop
    `target`. Returns (tabs, spaces, end_x). A tab advances to the next stop
    beyond the current position, so if `target` is already behind x the first
    tab lands on the next stop (whatever its kind); center/right text is
    aligned to the stop it lands on, unless it does not fit, in which case it
    starts at x. Beyond the last stop the text simply follows x (one tab).
    A center part that would come closer than MIN_GAP to x gets padding
    spaces (of width `space`) after the tab: they belong to the centered
    block, so the text starts after them."""
    ahead = [s for s in stops if s > x]
    if not ahead:
        return 1, 0, x + width
    tabs = ahead.index(target) + 1 if target in ahead else 1
    landed = ahead[tabs - 1]
    spaces = 0
    if landed == CENTER_STOP:
        def text_start(n):
            return max(x, landed - (width + n * space) / 2) + n * space
        while space > 0 and text_start(spaces) - x < MIN_GAP:
            spaces += 1
        start = text_start(spaces)
    elif landed == RIGHT_STOP:
        start = max(x, landed - width)
    else:
        start = landed
    return tabs, spaces, start + width


def row_tabs(left, center=None, right=None, width_fn=roboto_width):
    """Tab characters to insert before the center and the right part of a row
    laid out as `left <tabs> center <tabs> right` (parts are lists of Run).
    Returns (center_tabs, right_tabs, center_spaces): a missing part gives
    None tabs; center_spaces is the number of padding spaces to put after the
    center tabs, in the style of the last left run (0 if not needed). The tab
    count is at least 1 for a present part; the PDF check flags rows that
    still do not fit."""
    stops = sorted(LEFT_STOPS + (CENTER_STOP, RIGHT_STOP))
    x = runs_width(left, width_fn)
    space = width_fn(" ", left[-1].size, left[-1].bold) if left else 0.0
    center_tabs = right_tabs = None
    center_spaces = 0
    if center:
        center_tabs, center_spaces, x = _place(x, runs_width(center, width_fn),
                                               CENTER_STOP, stops, space)
    if right:
        right_tabs, _, _ = _place(x, runs_width(right, width_fn), RIGHT_STOP, stops)
    return center_tabs, right_tabs, center_spaces
