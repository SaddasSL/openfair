"""Text normalisation shared by extraction, de-duplication, reporting and scoring.

Engineering callouts arrive written many ways ("0.5" vs ".5", "Ø" vs "⌀",
symbols vs words). Everything that compares two callouts goes through here so
the rules live in one place and are unit tested.
"""
from __future__ import annotations

import re

DIAMETER_CHARS = "Ø⌀ø∅"

# GD&T characteristic -> symbols and words that identify it
GDT_CLASSES = {
    "position": ["⌖", "⊕", "position", "true position"],
    "perpendicularity": ["⊥", "perpendicularity", "perpendicular"],
    "parallelism": ["∥", "//", "parallelism", "parallel"],
    "angularity": ["∠", "angularity"],
    "straightness": ["⏤", "straightness"],
    "flatness": ["⏥", "▱", "flatness"],
    "circularity": ["○", "circularity", "roundness"],
    "cylindricity": ["⌭", "cylindricity"],
    "profile of a surface": ["⌓", "profile of a surface", "surface profile"],
    "profile of a line": ["⌒", "profile of a line", "line profile"],
    "concentricity": ["◎", "⊚", "concentricity"],
    "symmetry": ["⌯", "symmetry"],
    "circular runout": ["↗", "circular runout"],
    "total runout": ["⌰", "total runout"],
}

_NUMBER = re.compile(r"\d*\.\d+|\d+")
_LEADING_ZERO = re.compile(r"(?<![\d.])0+(?=\.\d)")


def clean(text: str | None) -> str:
    """Unify symbols and spacing without changing any number."""
    if not text:
        return ""
    s = str(text)
    for ch in DIAMETER_CHARS:
        s = s.replace(ch, "Ø")
    s = s.replace("±", "±").replace("−", "-").replace("–", "-").replace("×", "X")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def canonical(text: str | None) -> str:
    """Compact comparison form: no spaces or frame bars, leading zeros dropped.

    "Ø0.50 ±0.1" -> "Ø.50±.1". Only zeros *before* a decimal point that are not
    part of a larger number are removed, so 10.5 stays 10.5 (the previous
    `.replace("0.", ".")` turned 10.5 into 1.5).
    """
    s = clean(text).replace(" ", "").replace("|", "")
    return _LEADING_ZERO.sub("", s).upper()


def numbers(text: str | None) -> list[float]:
    """All numeric values in a callout, as floats (".438" and "0.438" are equal)."""
    return [float(n) for n in _NUMBER.findall(clean(text))]


def gdt_class(*texts: str | None) -> str | None:
    """Identify the GD&T characteristic named or drawn in any of the texts."""
    joined = " ".join(clean(t).lower() for t in texts if t)
    if not joined:
        return None
    # longest names first so "circular runout" wins over "circularity"
    candidates = sorted(((tok, name) for name, toks in GDT_CLASSES.items() for tok in toks),
                        key=lambda p: -len(p[0]))
    for tok, name in candidates:
        if tok.lower() in joined:
            return name
    return None


def datum_refs(text: str | None) -> list[str]:
    """Datum reference letters from a feature control frame, in order."""
    s = clean(text)
    if "|" not in s:
        # unframed text such as "⌖ Ø.05(M) A B(M) C(M)": letters after the tolerance value
        m = _NUMBER.search(s)
        if not m:
            return []
        tail = re.sub(r"\([MLSPF]\)|[ⓂⓁⓈⓅ]", " ", s[m.end():])
        tail = re.sub(r"\d*\.?\d+\s*X\s*\d*\.?\d+", " ", tail)  # per-unit-area ".25 X .25"
        return re.findall(r"(?<![A-Za-z0-9])([A-Z]\d?(?:-[A-Z]\d?)?)(?![A-Za-z0-9])", tail)
    refs = []
    for cell in s.split("|")[1:]:
        cell = re.sub(r"\(.*?\)|[ⓂⓁⓈⓅ]", "", cell).strip()
        if re.fullmatch(r"[A-Z](\d)?(-[A-Z]\d?)?", cell):
            refs.append(cell)
    return refs


def compatible_values(a: str | None, b: str | None) -> bool:
    """True when one callout text is the same as, or a truncation of, the other."""
    ca, cb = canonical(a), canonical(b)
    return bool(ca) and bool(cb) and (ca in cb or cb in ca)


def signature(entry: dict) -> tuple:
    """Order-independent identity of a characteristic, used for scoring.

    GD&T: (class, tolerance numbers, datum letters). Others: sorted numbers
    from value and tolerance (count prefixes such as 4X included).
    """
    value, tol = entry.get("value"), entry.get("tolerance")
    kind = entry.get("type")
    if kind == "gdt":
        frame = tol if tol and "|" in str(tol) else f"{value or ''} {tol or ''}"
        return ("gdt", gdt_class(value, tol), tuple(sorted(numbers(frame))), tuple(datum_refs(frame)))
    return ("dim", tuple(sorted(numbers(value) + numbers(tol))))
