"""First vision extraction: send a rendered drawing to Claude, get dimensions as JSON."""
import base64
import json
import os
import sys
from pathlib import Path

import anthropic

PROMPT = """You are an aerospace quality inspector analysing an engineering drawing.

Extract EVERY dimension, tolerance, and GD&T callout visible in this drawing.
Return ONLY a JSON array, no other text. Each element must have:
- "id": sequential integer starting at 1
- "type": one of "linear", "diameter", "radius", "angle", "gdt", "note"
- "value": the nominal value as written (e.g. "25.4", "R5", "⌀12")
- "tolerance": the tolerance as written (e.g. "±0.1", "+0.2/-0", or GD&T frame like "⌖ 0.2 (M) | A | B"), or null if none
- "zone": approximate location on the drawing (e.g. "top-left", "centre", "bottom-right")
- "bbox": approximate pixel bounding box of the callout text as [x, y, width, height],
  where x,y is the top-left corner. Estimate as accurately as you can.

CRITICAL - GD&T symbol identification. Look carefully at the symbol in the first
compartment of each feature control frame and use the correct one:
- ⌖ position (circle with crosshairs)
- ⊥ perpendicularity (upside-down T)
- ∥ parallelism, ∠ angularity, — straightness
- ⌭ cylindricity, ○ circularity, ⏥ flatness
- ⌓ profile of a surface (half circle), ⌒ profile of a line (arc)
- ⊙ concentricity, ⌯ symmetry, ↗ circular runout, ⌰ total runout
Do NOT default to position - perpendicularity ⊥ and position ⌖ look different.

Rules:
- A dimension with its feature control frame(s) and quantity note (e.g. 4X) is ONE
  logical callout: emit the dimension and each FCF as separate entries, but never
  split one FCF into fragments or re-emit part of a callout as its own entry.
- "nX" prefixes (2X, 4X) mean the dimension applies to n features - keep the prefix
  attached in "value" (e.g. "4X ⌀.625"), not as a separate note entry.
- A dimension like "4X .82" with no ⌀ symbol is linear spacing, NOT a diameter.
- Datum feature flags (boxed letters A, B, C...) attached to features: type "note",
  value "datum A" etc.

Be exhaustive - missing a characteristic on a FAIR is a quality escape."""


def extract(image_path: str) -> list[dict]:
    img = Path(image_path)
    data = base64.standard_b64encode(img.read_bytes()).decode()

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": "image/png", "data": data}},
                {"type": "text", "text": PROMPT},
            ],
        }],
    )
    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    return json.loads(text)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: py -m src.extraction.extract <image_path>")
        sys.exit(1)
    results = extract(sys.argv[1])
    out_path = Path("output") / (Path(sys.argv[1]).stem + "_extracted.json")
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Extracted {len(results)} characteristics -> {out_path}")
    for r in results:
        print(f"  #{r['id']:>3} [{r['type']}] {r['value']}  tol: {r['tolerance']}  ({r['zone']})")

