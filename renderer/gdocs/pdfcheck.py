"""PDF line analysis of position/project rows (FR-14, AC-9)."""

import unicodedata
from dataclasses import dataclass

LINE_TOLERANCE = 6.0  # pt: words whose `bottom` differs less are on one line
MIN_GAP = 6.0  # pt: minimum space between a row's text parts
ALIGN_TOLERANCE = 3.0  # pt: allowed deviation from the center/right tab stops
CENTER_STOP = 261  # pt from the left margin (template tab stops)
RIGHT_STOP = 553
HINT = "kézi döntés kell"
LEFT_MARGIN = 28.35  # pt: the template's left page margin (rows start there)
PAGE_STRIDE = 100000  # makes `top` unique across pages


@dataclass
class RowSpec:
    """Expected row: label identifies it in messages; `parts` are the three
    slots [left, center, right] (e.g. title, company, date); an unused slot
    is None/empty (a project row is [name, None, location])."""
    label: str
    parts: list


def extract_words(pdf_path):
    """Words of a PDF as dicts {text, x0, x1, top, bottom}, in reading order;
    vertical positions are offset per page so that lines of different pages
    never merge. x_tolerance=1 keeps nearly touching parts as separate words."""
    import pdfplumber
    words = []
    with pdfplumber.open(pdf_path) as pdf:
        for index, page in enumerate(pdf.pages):
            for w in page.extract_words(x_tolerance=1):
                words.append({"text": w["text"], "x0": w["x0"], "x1": w["x1"],
                              "top": w["top"] + index * PAGE_STRIDE,
                              "bottom": w["bottom"] + index * PAGE_STRIDE})
    return words


def _norm(text):
    return unicodedata.normalize("NFC", text)


def _find(words, tokens, start):
    """Index of the first run of words equal to `tokens` at or after `start`."""
    for i in range(start, len(words) - len(tokens) + 1):
        if all(_norm(words[i + j]["text"]) == tokens[j] for j in range(len(tokens))):
            return i
    return None


def analyze_rows(words, rows):
    """Check the rows (in document order) against the extracted words.
    Returns (issues, right_edges): Hungarian issue strings identifying the row
    (each ends with „kézi döntés kell”), and per row the x1 of its last word
    (None if the row was not found). Checks: one line, minimum gap between the
    parts, center part midpoint not more than 3 pt left of margin+261 (right of
    it is allowed: a long left part pushes it), right part's right edge
    within ±3 pt of margin+553 (margin = x0 of the left part, or LEFT_MARGIN
    without one). A row without any text is skipped (edge None)."""
    issues, right_edges = [], []
    pos = 0
    for row in rows:
        slots = [_norm(p).split() if p and p.strip() else [] for p in row.parts]
        tokens = [t for part in slots for t in part]
        if not tokens:  # nothing to look for
            right_edges.append(None)
            continue
        start = _find(words, tokens, pos)
        if start is None:
            issues.append(f"{row.label}: a sor szövege nem található a PDF-ben, {HINT}.")
            right_edges.append(None)
            continue
        pos = start + len(tokens)
        row_words = words[start:pos]
        right_edges.append(row_words[-1]["x1"])
        bottoms = [w["bottom"] for w in row_words]
        if max(bottoms) - min(bottoms) > LINE_TOLERANCE:
            issues.append(f"{row.label}: a sor több sorba tört, {HINT}.")
            continue
        offset = 0
        spans = {}  # slot index -> (x0, x1)
        for i, part in enumerate(slots):
            if part:
                chunk = row_words[offset:offset + len(part)]
                spans[i] = (chunk[0]["x0"], chunk[-1]["x1"])
                offset += len(part)
        ordered = [spans[i] for i in sorted(spans)]
        touching = False
        for (_, prev_end), (next_start, _) in zip(ordered, ordered[1:]):
            if next_start - prev_end < MIN_GAP:
                issues.append(f"{row.label}: a szövegrészek összeérnek "
                              f"(távolság {next_start - prev_end:.1f} pt), {HINT}.")
                touching = True
                break
        if touching:
            continue
        margin = spans[0][0] if 0 in spans else LEFT_MARGIN
        if 1 in spans:
            mid = (spans[1][0] + spans[1][1]) / 2
            # a center part pushed right by a long left part is fine (the gap
            # was checked above); left of the stop means a missing tab
            if mid - (margin + CENTER_STOP) < -ALIGN_TOLERANCE:
                issues.append(f"{row.label}: a középső rész nincs a középső tabstopon "
                              f"(eltérés {mid - margin - CENTER_STOP:+.1f} pt), {HINT}.")
        if 2 in spans:
            edge = spans[2][1]
            if abs(edge - (margin + RIGHT_STOP)) > ALIGN_TOLERANCE:
                issues.append(f"{row.label}: a jobb szél nincs a jobb tabstopon "
                              f"(eltérés {edge - margin - RIGHT_STOP:+.1f} pt), {HINT}.")
    return issues, right_edges


def check_pdf(pdf_path, rows):
    """analyze_rows over the words of a PDF file."""
    return analyze_rows(extract_words(pdf_path), rows)
