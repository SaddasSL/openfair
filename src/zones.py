"""Drawing grid zones for the Form 3 "Reference Location" field.

Inspectors locate a characteristic as sheet + zone, e.g. "Sh 1 / B3".

1. Detected grid: when the PDF text layer has zone labels around the border
   (single letters down the sides, numbers along the top/bottom), each point is
   assigned to the nearest label column and row.
2. Default grid: when no labels are found, the sheet is divided into a regular
   grid. The default follows ASME Y14.1 (numbers increase right to left from the
   lower right corner, letters increase upward); ISO 5457 style (numbers left to
   right, letters top to bottom) is available. Columns x rows can be overridden.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

EDGE = 0.06  # labels must sit within 6% of the sheet edge


@dataclass
class ZoneGrid:
    width: float
    height: float
    cols: list[tuple[float, str]]   # (x centre, label) in page units
    rows: list[tuple[float, str]]   # (y centre, label) in page units
    detected: bool

    def zone(self, x: float, y: float) -> str:
        col = min(self.cols, key=lambda c: abs(c[0] - x))[1]
        row = min(self.rows, key=lambda r: abs(r[0] - y))[1]
        return f"{row}{col}"


def detect_grid(pdf_page) -> ZoneGrid | None:
    """Read border zone labels from the PDF text layer, if the drawing has them."""
    W, H = pdf_page.rect.width, pdf_page.rect.height
    cols, rows = {}, {}
    for x0, y0, x1, y1, text, *_ in pdf_page.get_text("words"):
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        near_tb = cy < EDGE * H or cy > (1 - EDGE) * H
        near_lr = cx < EDGE * W or cx > (1 - EDGE) * W
        if near_tb and not near_lr and re.fullmatch(r"\d{1,2}", text):
            cols.setdefault(text, []).append(cx)
        elif near_lr and not near_tb and re.fullmatch(r"[A-HJ-NP-Z]", text):
            rows.setdefault(text, []).append(cy)
    if len(cols) < 2 or len(rows) < 2:
        return None
    return ZoneGrid(W, H,
                    sorted((sum(v) / len(v), k) for k, v in cols.items()),
                    sorted((sum(v) / len(v), k) for k, v in rows.items()),
                    detected=True)


def default_grid(width: float, height: float, cols: int | None = None,
                 rows: int | None = None, standard: str = "asme") -> ZoneGrid:
    """Regular grid when the drawing has no zone labels (sizes in PDF points)."""
    # roughly one zone per 4.25 in (306 pt), at least 2 x 2
    cols = cols or max(2, round(width / 306))
    rows = rows or max(2, round(height / 306))
    xs = [(i + 0.5) * width / cols for i in range(cols)]
    ys = [(j + 0.5) * height / rows for j in range(rows)]
    letters = [chr(ord("A") + k) for k in range(rows)]
    if standard == "iso":
        col_labels = [str(i + 1) for i in range(cols)]          # left to right
        row_labels = letters                                     # top to bottom
    else:
        col_labels = [str(cols - i) for i in range(cols)]       # right to left
        row_labels = list(reversed(letters))                     # bottom to top
    return ZoneGrid(width, height, list(zip(xs, col_labels)), list(zip(ys, row_labels)), detected=False)


def grid_for_page(pdf_page, override: str | None = None, standard: str = "asme") -> ZoneGrid:
    """Detected grid if present, else the default (or an override like "8x4")."""
    if not override:
        found = detect_grid(pdf_page)
        if found:
            return found
    cols = rows = None
    if override:
        m = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", override)
        if not m:
            raise ValueError(f"zones must look like 8x4, got {override!r}")
        cols, rows = int(m.group(1)), int(m.group(2))
    return default_grid(pdf_page.rect.width, pdf_page.rect.height, cols, rows, standard)


def reference_location(sheet: int, grid: ZoneGrid, bbox, dpi: int = 300) -> str:
    """'Sh 1 / B3' for a pixel bbox on a page rendered at dpi."""
    s = 72 / dpi
    x, y = (bbox[0] + bbox[2] / 2) * s, (bbox[1] + bbox[3] / 2) * s
    return f"Sh {sheet} / {grid.zone(x, y)}"
