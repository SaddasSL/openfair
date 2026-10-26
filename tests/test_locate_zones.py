import cv2
import fitz
import numpy as np

from src.ballooning.locate import locate
from src.zones import default_grid, grid_for_page, reference_location
from tests.conftest import SAMPLES


def test_text_layer_finds_black_callouts(black_drawing, tmp_path):
    doc = fitz.open(black_drawing)
    img = tmp_path / "p.png"
    doc[0].get_pixmap(dpi=300).save(img)
    s = 300 / 72
    entries = [{"type": "linear", "value": "25.40", "tolerance": "±0.10", "bbox": [420 * s + 60, 290 * s + 50, 200, 40]}]
    counts = locate(entries, str(img), doc[0])
    assert counts["pdf-text"] == 1
    x, y, w, h = entries[0]["bbox"]
    assert abs(x - 420 * s) < 30 and abs((y + h / 2) - 296 * s) < 40


def test_blank_page_falls_back_without_crashing(tmp_path):
    img = tmp_path / "blank.png"
    cv2.imwrite(str(img), np.full((2550, 3300, 3), 255, np.uint8))
    entries = [{"type": "linear", "value": "1.00", "bbox": [100, 100, 50, 20]}, {"type": "linear", "value": "2"}]
    counts = locate(entries, str(img))
    assert counts["estimate"] == 1 and counts["none"] == 1
    assert entries[0]["bbox"] == [100, 100, 50, 20]


def test_image_only_black_drawing_uses_dark_ink(tmp_path):
    """Scanned style drawing: no text layer, black ink only."""
    src = fitz.open(SAMPLES / "nist_ctc3.pdf")[0].get_pixmap(dpi=300)
    img = tmp_path / "gray.png"
    gray = cv2.cvtColor(np.frombuffer(src.samples, np.uint8).reshape(src.h, src.w, src.n)[:, :, :3], cv2.COLOR_RGB2GRAY)
    cv2.imwrite(str(img), gray)
    entries = [{"type": "diameter", "value": "Ø2.00", "tolerance": "±.01", "bbox": [1700, 700, 150, 50]}]
    counts = locate(entries, str(img))
    assert sum(counts.values()) == 1 and entries[0]["bbox_source"] in ("ink-dark", "estimate")


def test_zone_labels_detected(black_drawing):
    page = fitz.open(black_drawing)[0]
    grid = grid_for_page(page)
    assert grid.detected
    s = 300 / 72
    # x=120pt is in the leftmost column ("4"), y=150pt in the upper row ("B")
    assert reference_location(1, grid, [120 * s, 140 * s, 10, 10]) == "Sh 1 / B4"
    assert reference_location(1, grid, [700 * s, 500 * s, 10, 10]) == "Sh 1 / A1"


def test_default_grid_conventions():
    asme = default_grid(792, 612, 4, 2)
    iso = default_grid(792, 612, 4, 2, "iso")
    assert asme.zone(780, 600) == "A1" and asme.zone(10, 10) == "B4"
    assert iso.zone(10, 10) == "A1" and iso.zone(780, 600) == "B4"


def test_override_grid(black_drawing):
    grid = grid_for_page(fitz.open(black_drawing)[0], "8x4")
    assert not grid.detected and len(grid.cols) == 8 and len(grid.rows) == 4


def test_search_tokens_skip_short_fragments():
    from src.ballooning.locate import search_tokens
    assert "2" not in search_tokens({"value": "2 COPLANAR SURFACES", "tolerance": "⌓ | .01 | A"})
    assert search_tokens({"value": "R5"}) == ["R5"]
