"""Tab computation for position/project rows (FR-13) from Roboto font metrics."""

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont

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


def _place(x, width, target, stops):
    """Place a part of `width` after position x using tabs aimed at stop
    `target`. Returns (tabs, end_x). A tab advances to the next stop beyond
    the current position, so if `target` is already behind x the first tab
    lands on the next stop (whatever its kind); center/right text is aligned
    to the stop it lands on, unless it does not fit, in which case it starts
    at x. Beyond the last stop the text simply follows x (one tab)."""
    ahead = [s for s in stops if s > x]
    if not ahead:
        return 1, x + width
    tabs = ahead.index(target) + 1 if target in ahead else 1
    landed = ahead[tabs - 1]
    if landed == CENTER_STOP:
        start = max(x, landed - width / 2)
    elif landed == RIGHT_STOP:
        start = max(x, landed - width)
    else:
        start = landed
    return tabs, start + width


def row_tabs(left, center=None, right=None, width_fn=roboto_width):
    """Tab characters to insert before the center and the right part of a row
    laid out as `left <tabs> center <tabs> right` (parts are lists of Run).
    Returns (center_tabs, right_tabs); a missing part gives None. The count is
    at least 1 for a present part; the PDF check flags rows that still do
    not fit."""
    stops = sorted(LEFT_STOPS + (CENTER_STOP, RIGHT_STOP))
    x = runs_width(left, width_fn)
    center_tabs = right_tabs = None
    if center:
        center_tabs, x = _place(x, runs_width(center, width_fn), CENTER_STOP, stops)
    if right:
        right_tabs, _ = _place(x, runs_width(right, width_fn), RIGHT_STOP, stops)
    return center_tabs, right_tabs
