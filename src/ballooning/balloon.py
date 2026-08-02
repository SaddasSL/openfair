"""Draw numbered inspection balloons on a drawing using extracted bbox positions."""
import json
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RADIUS = 28
COLOR = (200, 0, 0)  # red


def is_ballooned(entry: dict) -> bool:
    """Datum flags are not inspection characteristics - no balloon."""
    if entry.get("type") == "note" and (entry.get("value") or "").lower().startswith("datum"):
        return False
    return True


def load_font(size: int):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)
    except OSError:
        return ImageFont.load_default()


def balloon(image_path: str, json_path: str) -> Path:
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font(int(RADIUS * 1.1))

    entries = json.loads(Path(json_path).read_text(encoding="utf-8"))

    # group entries by their (snapped) bbox so shared clusters stack balloons
    groups = defaultdict(list)
    number = 0
    for e in entries:
        if not is_ballooned(e):
            continue
        number += 1
        e["balloon"] = number
        groups[tuple(e["bbox"])].append(e)

    for bbox, members in groups.items():
        x, y, bw, bh = bbox
        cx = max(RADIUS + 2, x - RADIUS - 8)
        n = len(members)
        for i, e in enumerate(members):
            # stack vertically, centred on the cluster
            cy = y + bh / 2 + (i - (n - 1) / 2) * (2 * RADIUS + 8)
            cy = min(max(RADIUS + 2, cy), img.height - RADIUS - 2)
            draw.ellipse((cx - RADIUS, cy - RADIUS, cx + RADIUS, cy + RADIUS),
                         outline=COLOR, width=4, fill=(255, 255, 255))
            draw.text((cx, cy), str(e["balloon"]), fill=COLOR, font=font, anchor="mm")
            if i == 0:
                draw.line((cx + RADIUS, y + bh / 2, x, y + bh / 2), fill=COLOR, width=3)

    out = Path(json_path).with_name(Path(image_path).stem + "_ballooned.png")
    img.save(out)
    Path(json_path).write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                               encoding="utf-8")
    print(f"{number} balloons drawn -> {out}")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: py -m src.ballooning.balloon <image_path> <extracted_json>")
        sys.exit(1)
    balloon(sys.argv[1], sys.argv[2])
