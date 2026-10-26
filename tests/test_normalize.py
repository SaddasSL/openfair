from src import normalize


def test_leading_zero_only():
    assert normalize.canonical("0.5") == normalize.canonical(".5")
    assert normalize.canonical("10.5") == "10.5"          # was corrupted to 1.5
    assert normalize.canonical("100.25") == "100.25"
    assert normalize.canonical("⌀20.0") == "Ø20.0"


def test_numbers_and_symbols():
    assert normalize.numbers("4X Ø.625 ±.005") == [4, 0.625, 0.005]
    assert normalize.gdt_class("↗ .025 | A-B") == "circular runout"
    assert normalize.gdt_class("○ .002") == "circularity"
    assert normalize.gdt_class("⌰ .015 | B") == "total runout"


def test_datums():
    assert normalize.datum_refs("⌖ Ø.05(M) | A | B(M) | C(M)") == ["A", "B", "C"]
    assert normalize.datum_refs("⌖ Ø.05(M) A B(M) C(M)") == ["A", "B", "C"]
    assert normalize.datum_refs("⏥ .005 / .25 X .25") == []


def test_signature_ignores_formatting():
    a = {"type": "gdt", "value": "position", "tolerance": "⌖ Ø.05(M) | A | B(M) | C(M)"}
    b = {"type": "gdt", "value": "⌖ Ø0.05Ⓜ | A | BⓂ | CⓂ", "tolerance": None}
    assert normalize.signature(a) == normalize.signature(b)
    assert normalize.signature({"type": "diameter", "value": "Ø10.5", "tolerance": "±.1"}) != \
        normalize.signature({"type": "diameter", "value": "Ø1.5", "tolerance": "±.1"})


def test_signature_counts_repeated_tolerance_once():
    in_value = {"type": "diameter", "value": "2X Ø.438 ±.005", "tolerance": "±.005"}
    separate = {"type": "diameter", "value": "2X Ø.438", "tolerance": "±.005"}
    assert normalize.signature(in_value) == normalize.signature(separate)


def test_signature_trusts_the_frame_symbol():
    loose = {"type": "gdt", "value": "↗↗ .002", "tolerance": "⌰ | .002 | A"}
    key = {"type": "gdt", "value": "total runout", "tolerance": "⌰ .002 | A"}
    assert normalize.signature(loose) == normalize.signature(key)
