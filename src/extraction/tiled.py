"""Tiled extraction with deterministic ownership-based merging (no LLM merge)."""
import json
import sys
from pathlib import Path

from PIL import Image

from src.extraction.extract import extract

ROWS, COLS = 2, 3
OVERLAP = 0.2  # tiles extend 20% past their ownership region


def tile_image(image_path: str, out_dir: str = "output"):
    """Yield (name, tile_path, (ox, oy), ownership_box_global)."""
    img = Image.open(image_path)
    w, h = img.size
    cell_w, cell_h = w / COLS, h / ROWS
    pad_x, pad_y = cell_w * OVERLAP, cell_h * OVERLAP
    stem = Path(image_path).stem
    tiles = []
    for r in range(ROWS):
        for c in range(COLS):
            own = (c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h)
            x0 = max(0, int(own[0] - pad_x))
            y0 = max(0, int(own[1] - pad_y))
            x1 = min(w, int(own[2] + pad_x))
            y1 = min(h, int(own[3] + pad_y))
            name = f"r{r + 1}c{c + 1}"
            p = Path(out_dir) / f"{stem}_tile_{name}.png"
            img.crop((x0, y0, x1, y1)).save(p)
            tiles.append((name, p, (x0, y0), own))
    print(f"{len(tiles)} tiles written (~{x1 - x0}x{y1 - y0}px each)")
    return tiles


def centre(bbox):
    return bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2


def norm(entry):
    v = (entry.get("value") or "").replace(" ", "")
    t = (entry.get("tolerance") or "").replace(" ", "")
    return f"{entry.get('type')}|{v}|{t}"


def merge_tiles(image_path: str) -> list[dict]:
    kept = []
    for name, path, (ox, oy), own in tile_image(image_path):
        results = extract(str(path))
        owned = 0
        for e in results:
            bbox = e.get("bbox")
            if not bbox or len(bbox) != 4:
                continue  # no position info - cannot place or dedupe reliably
            gx, gy = bbox[0] + ox, bbox[1] + oy
            e["bbox"] = [gx, gy, bbox[2], bbox[3]]
            cx, cy = centre(e["bbox"])
            if own[0] <= cx < own[2] and own[1] <= cy < own[3]:
                e["tile"] = name
                kept.append(e)
                owned += 1
        print(f"  {name}: {len(results)} extracted, {owned} owned")

    # safety dedupe: identical normalized text with nearly coincident boxes
    final = []
    for e in kept:
        dup = next((f for f in final if norm(f) == norm(e)
                    and abs(centre(f["bbox"])[0] - centre(e["bbox"])[0]) < 150
                    and abs(centre(f["bbox"])[1] - centre(e["bbox"])[1]) < 150), None)
        if not dup:
            final.append(e)
    for i, e in enumerate(final, start=1):
        e["id"] = i
    return final


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py -m src.extraction.tiled <image_path>")
        sys.exit(1)
    results = merge_tiles(sys.argv[1])
    out_path = Path("output") / (Path(sys.argv[1]).stem + "_tiled.json")
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nMerged total: {len(results)} characteristics -> {out_path}")
    for r in results:
        print(f"  #{r['id']:>3} [{r['type']}] {r['value']}  tol: {r['tolerance']}  ({r['zone']}, {r['tile']})")
