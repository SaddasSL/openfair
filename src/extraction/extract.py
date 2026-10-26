"""Vision extraction: send a rendered drawing (or a tile of one) to the model, get JSON back."""
from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path

MODEL = os.environ.get("OPENFAIR_MODEL", "claude-sonnet-4-6")

PROMPT = """You are an aerospace quality inspector analysing an engineering drawing.

Extract EVERY dimension, tolerance, and GD&T callout visible in this image.
Return ONLY a JSON array, no other text. Each element must have:
- "id": sequential integer starting at 1
- "type": one of "linear", "diameter", "radius", "angle", "thread", "gdt", "note"
- "value": the callout as written (e.g. "25.4", "R5", "4X Ø.625", "M12 x 1.75 - 6H")
- "tolerance": the tolerance as written (e.g. "±0.1", "+0.2/-0"), or for a feature
  control frame the whole frame with cells separated by | (e.g. "⌖ Ø0.2(M) | A | B"),
  or null if none
- "basic": true if the dimension is boxed (basic), otherwise false
- "reference": true if the dimension is in parentheses (reference), otherwise false
- "key": true if the drawing flags it as a key or critical characteristic, otherwise false
- "bbox": pixel bounding box of the callout text as [x, y, width, height] in this
  image, x,y = top-left corner. Estimate as accurately as you can.

CRITICAL - GD&T symbol identification. Use the symbol in the first cell of each frame:
- ⌖ position (circle with crosshairs)      - ⊥ perpendicularity (upside-down T)
- ∥ parallelism, ∠ angularity, ⏤ straightness
- ⌭ cylindricity, ○ circularity, ⏥ flatness
- ⌓ profile of a surface (closed half circle), ⌒ profile of a line (open arc)
- ◎ concentricity, ⌯ symmetry, ↗ circular runout (one arrow), ⌰ total runout (two arrows)
Do NOT default to position - perpendicularity ⊥ and position ⌖ look different.

Rules:
- A dimension and its feature control frame(s) are separate entries; never split one
  frame into fragments. A composite frame (two rows sharing one symbol) is two entries.
- Keep "nX" quantity prefixes (2X, 4X) inside "value", e.g. "4X Ø.625".
- A dimension like "4X .82" with no Ø symbol is linear spacing, NOT a diameter.
- Datum feature symbols (boxed letters) and datum targets: type "note", value "datum A".
- Do not report title block text, view labels or general notes here.

Be exhaustive - missing a characteristic on a FAIR is a quality escape."""

TITLE_PROMPT = """You are reading the title block and notes of an engineering drawing.
Return ONLY a JSON object with these keys (null when not shown):
"part_number", "part_name", "drawing_number", "revision", "material",
"specifications": list of material, process or finish specifications cited
  (e.g. "AMS 2700 Method 1", "MIL-A-8625 Type II"), each as
  {"name": short description, "spec": specification number, "type": "material" | "process" | "finish" | "test"},
"notes": list of general notes as written."""


def _client():
    import anthropic  # imported lazily so offline tools and tests don't need it
    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment


def _ask(image_path: str | Path, prompt: str, max_tokens: int = 8000) -> str:
    data = base64.standard_b64encode(Path(image_path).read_bytes()).decode()
    message = _client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}},
            {"type": "text", "text": prompt},
        ]}],
    )
    return message.content[0].text


def parse_json(text: str):
    """Pull the JSON payload out of a model reply, tolerating code fences or prose."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
        end = max(text.rfind("]"), text.rfind("}"))
        if start < 0 or end <= start:
            raise
        return json.loads(text[start:end + 1])


def extract(image_path: str) -> list[dict]:
    result = parse_json(_ask(image_path, PROMPT))
    if not isinstance(result, list):
        raise ValueError("model did not return a list of characteristics")
    return [r for r in result if isinstance(r, dict)]


def extract_title_block(image_path: str) -> dict:
    result = parse_json(_ask(image_path, TITLE_PROMPT, max_tokens=3000))
    return result if isinstance(result, dict) else {}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.extraction.extract <image_path>")
        sys.exit(1)
    results = extract(sys.argv[1])
    out_path = Path("output") / (Path(sys.argv[1]).stem + "_extracted.json")
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Extracted {len(results)} characteristics -> {out_path}")
