"""Tiled extraction: split drawing into overlapping tiles for full-resolution reading."""
import json
import sys
from pathlib import Path

import anthropic
from PIL import Image

from src.extraction.extract import extract

OVERLAP = 0.2  # 20% overlap between tiles

MERGE_PROMPT = """Below are JSON extraction results from 4 overlapping tiles of the SAME
engineering drawing (2x2 grid: top-left, top-right, bottom-left, bottom-right,
with 20% overlap between adjacent tiles).

Because tiles overlap, some characteristics were extracted twice from the
overlap zones - merge those into a single entry. BUT: characteristics with the
same value that exist at genuinely different locations on the drawing are NOT
duplicates - keep them as separate entries. Use each entry's tile of origin and
zone to decide: duplicates come from adjacent tiles' shared overlap region.

Return ONLY the merged JSON array, renumbering "id" sequentially from 1,
keeping the same schema (id, type, value, tolerance, zone). Rewrite "zone" to
describe position on the FULL drawing. Your entire response must be the JSON
array itself - no preamble, no explanation, no markdown fences.

"""


def parse_json_array(text: str) -> list[dict]:
    """Extract the first JSON array found in a model response."""
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON array in model response. First 300 chars:\n{text[:300]}")
    return json.loads(text[start:end + 1])


def tile_image(image_path: str, out_dir: str = "output") -> list[tuple[str, Path]]:
    img = Image.open(image_path)
    w, h = img.size
    tw, th = int(w * (0.5 + OVERLAP / 2)), int(h * (0.5 + OVERLAP / 2))
    boxes = {
        "top-left": (0, 0, tw, th),
        "top-right": (w - tw, 0, w, th),
        "bottom-left": (0, h - th, tw, h),
        "bottom-right": (w - tw, h - th, w, h),
    }
    stem = Path(image_path).stem
    tiles = []
    for name, box in boxes.items():
        p = Path(out_dir) / f"{stem}_tile_{name}.png"
        img.crop(box).save(p)
        tiles.append((name, p))
        print(f"Tile {name}: {p.name} ({box[2] - box[0]}x{box[3] - box[1]}px)")
    return tiles


def merge(tile_results: dict[str, list]) -> list[dict]:
    tiles_text = "\n\n".join(
        f"TILE {name}:\n{json.dumps(res, ensure_ascii=False)}"
        for name, res in tile_results.items()
    )
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{"role": "user", "content": MERGE_PROMPT + tiles_text}],
    )
    return parse_json_array(msg.content[0].text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py -m src.extraction.tiled <image_path>")
        sys.exit(1)

    tile_results = {}
    for name, path in tile_image(sys.argv[1]):
        print(f"Extracting {name}...")
        tile_results[name] = extract(str(path))
        print(f"  -> {len(tile_results[name])} characteristics")

    print("Merging tiles...")
    results = merge(tile_results)

    out_path = Path("output") / (Path(sys.argv[1]).stem + "_tiled.json")
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nMerged total: {len(results)} characteristics -> {out_path}")
    for r in results:
        print(f"  #{r['id']:>3} [{r['type']}] {r['value']}  tol: {r['tolerance']}  ({r['zone']})")
