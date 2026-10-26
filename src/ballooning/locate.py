"""Find where each characteristic sits on the page, without crashing.

The vision model returns an approximate box for every callout. This module
tightens it using, in order of preference:

1. the PDF text layer  - exact positions when the drawing was exported with real text
2. ink clusters        - OpenCV groups of annotation pixels in any colour (coloured
                         PMI is used when present, otherwise dark ink on a light sheet)
3. the model estimate  - kept as-is when nothing better is found nearby

Every entry gets "bbox_source" so the report shows how each position was found.
"""
from __future__ import annotations

import math
import re

import cv2
import numpy as np

from src import normalize

SEARCH_RADIUS = 0.08      # fraction of page diagonal to look around the estimate
MIN_CLUSTER_AREA = 400    # px at 300 DPI; smaller blobs are specks
MAX_CLUSTER_FRAC = 0.05   # clusters bigger than this share of the page are geometry


def _centre(b):
    return b[0] + b[2] / 2, b[1] + b[3] / 2


def _dist(a, b):
    (ax, ay), (bx, by) = _centre(a), _centre(b)
    return math.hypot(ax - bx, ay - by)


def search_tokens(entry: dict) -> list[str]:
    """Most distinctive strings to look for in the PDF text, best first."""
    text = f"{entry.get('value') or ''} {entry.get('tolerance') or ''}"
    words = [w for w in re.split(r"\s+", (entry.get("value") or "").strip()) if len(w) > 1]
    nums = re.findall(r"\d*\.\d+|\d+\.\d*|\d+", text)
    # whole words first (most specific), then numbers, longest first
    # one or two characters ("2", "A") match too many unrelated words on a sheet
    tokens = sorted(words, key=len, reverse=True) + sorted(set(nums), key=len, reverse=True)
    whole = (entry.get("value") or "").strip()
    return [t for t in dict.fromkeys(tokens) if len(t) >= 3 or (t == whole and len(t) >= 2)]


# ---------- 1. PDF text layer ----------

def text_layer_boxes(pdf_page, dpi: int = 300) -> list[tuple[str, list[float]]]:
    """Words on the page with pixel boxes at the render DPI."""
    s = dpi / 72
    return [(w[4], [w[0] * s, w[1] * s, (w[2] - w[0]) * s, (w[3] - w[1]) * s])
            for w in pdf_page.get_text("words")]


def locate_in_text(entry: dict, words, radius: float):
    est = entry.get("bbox")
    if not est:
        return None
    for token in search_tokens(entry):
        hits = [box for text, box in words if token in text]
        hits = [h for h in hits if _dist(h, est) <= radius]
        if hits:
            best = min(hits, key=lambda h: _dist(h, est))
            # grow the box with nearby words that belong to this callout's own text
            own = normalize.canonical(f"{entry.get('value') or ''}{entry.get('tolerance') or ''}")
            near = [best] + [box for text, box in words
                             if _dist(box, best) <= 0.3 * radius and normalize.canonical(text)
                             and normalize.canonical(text) in own]
            x0 = min(b[0] for b in near); y0 = min(b[1] for b in near)
            x1 = max(b[0] + b[2] for b in near); y1 = max(b[1] + b[3] for b in near)
            return [round(x0), round(y0), round(x1 - x0), round(y1 - y0)]
    return None


# ---------- 2. ink clusters ----------

def annotation_mask(img: np.ndarray) -> tuple[np.ndarray, str]:
    """Pixels that are probably annotation ink, and which rule found them."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    coloured = cv2.inRange(hsv, np.array([0, 90, 60]), np.array([179, 255, 255]))
    # coloured PMI (e.g. blue model-based annotations): use it when there is enough of it
    if cv2.countNonZero(coloured) > 0.002 * coloured.size:
        return coloured, "colour"
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, dark = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return dark, "dark"


def find_clusters(img: np.ndarray) -> tuple[list[list[int]], str]:
    mask, rule = annotation_mask(img)
    # long straight segments are leaders, extension lines or part edges - not text
    lines = cv2.HoughLinesP(mask, 1, np.pi / 180, threshold=80, minLineLength=60, maxLineGap=4)
    if lines is not None:
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            cv2.line(mask, (int(x1), int(y1)), (int(x2), int(y2)), 0, 7)
    fused = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25)))
    n, _, stats, _ = cv2.connectedComponentsWithStats(fused)
    limit = MAX_CLUSTER_FRAC * mask.size
    clusters = [[int(x), int(y), int(w), int(h)]
                for x, y, w, h, area in stats[1:] if MIN_CLUSTER_AREA <= area <= limit]
    return clusters, rule


def locate_in_clusters(entry: dict, clusters, radius: float):
    est = entry.get("bbox")
    if not est or not clusters:
        return None
    near = [c for c in clusters if _dist(c, est) <= radius]
    if not near:
        return None

    def overlap(c):
        x0, y0 = max(c[0], est[0]), max(c[1], est[1])
        x1, y1 = min(c[0] + c[2], est[0] + est[2]), min(c[1] + c[3], est[1] + est[3])
        return max(0, x1 - x0) * max(0, y1 - y0)

    return max(near, key=lambda c: (overlap(c), -_dist(c, est)))


# ---------- combined ----------

def locate(entries: list[dict], image_path: str, pdf_page=None, dpi: int = 300) -> dict:
    """Update each entry's bbox in place. Returns a count per method."""
    img = cv2.imread(str(image_path))
    if img is None:
        raise FileNotFoundError(image_path)
    h, w = img.shape[:2]
    radius = SEARCH_RADIUS * math.hypot(w, h)
    words = text_layer_boxes(pdf_page, dpi) if pdf_page is not None else []
    clusters, rule = find_clusters(img)
    counts = {"pdf-text": 0, f"ink-{rule}": 0, "estimate": 0, "none": 0}
    for e in entries:
        if not e.get("bbox"):
            e["bbox_source"] = "none"
            counts["none"] += 1
            continue
        e.setdefault("bbox_estimate", [int(v) for v in e["bbox"]])
        box = locate_in_text(e, words, radius) if words else None
        source = "pdf-text"
        if box is None:
            box, source = locate_in_clusters(e, clusters, radius), f"ink-{rule}"
        if box is None:
            box, source = e["bbox"], "estimate"
        e["bbox"] = [int(v) for v in box]
        e["bbox_source"] = source
        counts[source] += 1
    return counts
