import sys
from pathlib import Path

import fitz
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SAMPLES = ROOT / "samples" / "public"

CALLOUTS = [  # (text, x, y) in PDF points on a letter landscape sheet
    ("Ø10.5 ±0.1", 120, 150),
    ("Ø1.5 ±0.05", 170, 150),     # close to the one above; must NOT be merged with it
    ("25.40 ±0.10", 420, 300),
    ("R5", 600, 450),
]


@pytest.fixture
def black_drawing(tmp_path):
    """A plain black-ink drawing with a real text layer and border zone labels."""
    path = tmp_path / "black.pdf"
    doc = fitz.open()
    page = doc.new_page(width=792, height=612)
    page.draw_rect(fitz.Rect(30, 30, 762, 582), color=(0, 0, 0), width=1)
    page.draw_rect(fitz.Rect(150, 200, 650, 420), color=(0, 0, 0), width=2)   # the "part"
    for i, n in enumerate("4321"):                     # ASME style: numbers right to left
        page.insert_text((30 + (i + 0.5) * 183, 24), n, fontsize=9)
        page.insert_text((30 + (i + 0.5) * 183, 596), n, fontsize=9)
    for j, letter in enumerate("BA"):                  # letters bottom to top
        page.insert_text((14, 30 + (j + 0.5) * 276), letter, fontsize=9)
        page.insert_text((770, 30 + (j + 0.5) * 276), letter, fontsize=9)
    for text, x, y in CALLOUTS:
        page.insert_text((x, y), text, fontsize=11)
    doc.save(path)
    return path


def fake_extractor_for(callouts, dpi=300, offset=40):
    """Stands in for the vision model: returns the callouts with slightly wrong boxes."""
    s = dpi / 72

    def extract(tile_path):
        import re
        from PIL import Image
        m = re.search(r"_tile_r(\d)c(\d)", str(tile_path))
        r, c = int(m.group(1)), int(m.group(2))
        # reproduce tiled.tile_image geometry for a 3300x2550 page
        W, H = 792 * s, 612 * s
        cw, ch = W / 3, H / 2
        x0, y0 = max(0, int((c - 1) * cw - cw * 0.2)), max(0, int((r - 1) * ch - ch * 0.2))
        tw, th = Image.open(tile_path).size
        out = []
        for i, (text, x, y) in enumerate(callouts, 1):
            px, py = x * s - x0 + offset, (y - 10) * s - y0 + offset
            if 0 <= px < tw and 0 <= py < th:
                value, _, tol = text.partition(" ")
                kind = "diameter" if value.startswith("Ø") else "radius" if value.startswith("R") else "linear"
                out.append({"id": i, "type": kind, "value": value, "tolerance": tol or None,
                            "bbox": [px, py, len(text) * 18, 40]})
        return out
    return extract
