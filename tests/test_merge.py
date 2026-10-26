from src.extraction.tiled import merge


def e(value, tol, x, y, kind="diameter"):
    return {"type": kind, "value": value, "tolerance": tol, "bbox": [x, y, 100, 30]}


def test_distinct_numbers_are_not_merged():
    out = merge([e("Ø10.5", "±0.1", 100, 100), e("Ø1.5", "±0.1", 150, 100)], (3300, 2550))
    assert len(out) == 2


def test_same_callout_from_two_tiles_is_merged_keeping_fuller_reading():
    out = merge([e("Ø.438", None, 100, 100), e("2X Ø0.438", "±.005", 120, 105)], (3300, 2550))
    assert len(out) == 1 and out[0]["tolerance"] == "±.005"


def test_far_apart_identical_callouts_are_both_kept():
    out = merge([e("Ø.438", "±.005", 100, 100), e("Ø.438", "±.005", 2500, 2000)], (3300, 2550))
    assert len(out) == 2


def test_composite_frame_segments_are_kept():
    a = {"type": "gdt", "value": "position", "tolerance": "⌖ Ø1.5 | D | E | F", "bbox": [100, 100, 200, 30]}
    b = {"type": "gdt", "value": "position", "tolerance": "⌖ Ø0.3 | D | E", "bbox": [100, 130, 200, 30]}
    assert len(merge([a, b], (3300, 2550))) == 2
