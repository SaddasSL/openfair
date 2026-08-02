"""Draw numbered inspection balloons on a drawing using extracted bbox positions."""
import json
import sys
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
    number = 0
    for e in entries:
        if not is_ballooned(e):
            continue
        number += 1
        e["balloon"] = number
        x, y, bw, bh = e["bbox"]
        # balloon centre: just left of the callout, vertically centred on it
        cx, cy = x - RADIUS - 8, y + bh / 2
        cx = max(RADIUS + 2, cx)
        draw.ellipse((cx - RADIUS, cy - RADIUS, cx + RADIUS, cy + RADIUS),
                     outline=COLOR, width=4, fill=(255, 255, 255))
        draw.text((cx, cy), str(number), fill=COLOR, font=font, anchor="mm")
        # short leader line to the callout's left edge
        draw.line((cx + RADIUS, cy, x, cy), fill=COLOR, width=3)

    out = Path(json_path).with_name(Path(image_path).stem + "_ballooned.png")
    img.save(out)
    # save back the JSON with balloon numbers - the FAIR form will use these
    Path(json_path).write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                               encoding="utf-8")
    print(f"{number} balloons drawn -> {out}")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: py -m src.ballooning.balloon <image_path> <extracted_json>")
        sys.exit(1)
    balloon(sys.argv[1], sys.argv[2])
