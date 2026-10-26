"""Tiled extraction with deterministic ownership-based merging.

The page is cut into overlapping tiles so small callouts are read at full
resolution. Each tile only keeps callouts whose centre lies in its own cell,
then near-identical callouts that straddle a boundary are merged.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from PIL import Image

from src import normalize

ROWS, COLS = 2, 3
OVERLAP = 0.2          # tiles extend 20% past their ownership cell
DEDUPE_RADIUS = 0.06   # fraction of the page diagonal


def tile_image(image_path: str, out_dir: str | None = None):
    """Return [(name, tile_path, (ox, oy), ownership_box)] for one page image."""
    img = Image.open(image_path)
    w, h = img.size
    out = Path(out_dir) if out_dir else Path(image_path).parent
    cell_w, cell_h = w / COLS, h / ROWS
    pad_x, pad_y = cell_w * OVERLAP, cell_h * OVERLAP
    tiles = []
    for r in range(ROWS):
        for c in range(COLS):
            own = (c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h)
            x0, y0 = max(0, int(own[0] - pad_x)), max(0, int(own[1] - pad_y))
            x1, y1 = min(w, int(own[2] + pad_x)), min(h, int(own[3] + pad_y))
            name = f"r{r + 1}c{c + 1}"
            p = out / f"{Path(image_path).stem}_tile_{name}.png"
            img.crop((x0, y0, x1, y1)).save(p)
            tiles.append((name, p, (x0, y0), own))
    return tiles


def centre(bbox):
    return bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2


def _valid_bbox(b) -> bool:
    return isinstance(b, (list, tuple)) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b)


def completeness(e: dict) -> int:
    return len(e.get("value") or "") + len(e.get("tolerance") or "")


def is_duplicate(a: dict, b: dict, radius: float) -> bool:
    """Same callout read twice: same type, compatible text, nearby centres."""
    if a.get("type") != b.get("type"):
        return False
    if not (normalize.compatible_values(a.get("value"), b.get("value"))
            and (not a.get("tolerance") or not b.get("tolerance")
                 or normalize.compatible_values(a.get("tolerance"), b.get("tolerance")))):
        return False
    (ax, ay), (bx, by) = centre(a["bbox"]), centre(b["bbox"])
    return math.hypot(ax - bx, ay - by) <= radius


def merge(entries: list[dict], page_size: tuple[int, int]) -> list[dict]:
    """Collapse duplicates, keeping the most complete reading. Order is preserved."""
    radius = DEDUPE_RADIUS * math.hypot(*page_size)
    final: list[dict] = []
    for e in entries:
        dup = next((f for f in final if is_duplicate(f, e, radius)), None)
        if dup is None:
            final.append(e)
        elif completeness(e) > completeness(dup):
            final[final.index(dup)] = e
    return final


def merge_tiles(image_path: str, extractor=None) -> list[dict]:
    """Extract one page image tile by tile and merge the results."""
    if extractor is None:
        from src.extraction.extract import extract as extractor
    w, h = Image.open(image_path).size
    kept = []
    for name, path, (ox, oy), own in tile_image(image_path):
        results = extractor(str(path))
        owned = 0
        for e in results:
            if not _valid_bbox(e.get("bbox")):
                continue  # no position: cannot assign to a tile or dedupe safely
            b = e["bbox"]
            e["bbox"] = [b[0] + ox, b[1] + oy, b[2], b[3]]
            cx, cy = centre(e["bbox"])
            if own[0] <= cx < own[2] and own[1] <= cy < own[3]:
                e["tile"] = name
                kept.append(e)
                owned += 1
        print(f"  {name}: {len(results)} extracted, {owned} owned")
    return merge(kept, (w, h))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.extraction.tiled <image_path>")
        sys.exit(1)
    results = merge_tiles(sys.argv[1])
    for i, e in enumerate(results, 1):
        e["id"] = i
    out_path = Path(sys.argv[1]).with_name(Path(sys.argv[1]).stem + "_tiled.json")
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nMerged total: {len(results)} characteristics -> {out_path}")
