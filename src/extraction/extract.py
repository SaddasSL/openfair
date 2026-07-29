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
    for r in results[:10]:
        print(f"  #{r['id']:>3} [{r['type']}] {r['value']}  tol: {r['tolerance']}  ({r['zone']})")
