# OpenFAIR

Open-source AS9102 First Article Inspection Report (FAIR) generator.

Give it an engineering drawing PDF and it returns:

- **a ballooned drawing** (PDF, every page) with each characteristic numbered
- **an AS9102 workbook** with Form 1 (Part Number Accountability), Form 2 (Product
  Accountability) and Form 3 (Characteristic Accountability), plus an inspection plan
  sheet with calculated upper and lower limits
- **a characteristics file** (JSON) you can correct by hand and rebuild from

Built by an aerospace quality inspector who got tired of ballooning drawings by hand.

## How it works

| Step | What happens |
|---|---|
| Render | Every page of the PDF is rendered at 300 DPI. |
| Extract | Each page is cut into 6 overlapping tiles and read by a vision model, which returns every dimension, tolerance, thread and feature control frame. Tiles keep only callouts centred in their own cell, then readings that straddle a boundary are merged. The title block (part number, revision, material, specifications) is read from page 1. |
| Locate | Each callout's position is tightened using the PDF text layer when the drawing has real text, otherwise OpenCV ink clusters (coloured PMI or black ink), otherwise the model's estimate is kept. Nothing found never stops the run. |
| Zones | Reference Location is written as sheet and zone, e.g. `Sh 1 / B3`. Zone labels are read from the drawing border when present; otherwise a regular grid is used (ASME Y14.1 numbering by default, ISO 5457 optional, or set your own size). |
| Balloon | Characteristics are numbered in page order. Datum symbols, notes, basic and reference dimensions get no balloon. Each balloon goes in the nearest clear space beside its own callout, so it stays readable on angled and crowded views. |
| Report | Forms 1 to 3 are filled from the title block and the characteristics. Results, serial numbers and signatures are left for the inspector. |

## Quick start

```
python -m venv venv
venv\Scripts\activate            # Windows  (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
set OPENFAIR_API_KEY=...          # export on macOS/Linux; needed for extraction only

python -m src.pipeline samples/public/nist_ctc3.pdf --part-number CTC-3 --part-name "Test model 3"
```

Options: `--out DIR`, `--order-number`, `--zones 8x4` (force a grid), `--zone-standard iso`,
and `--from-json file_characteristics.json` to rebuild the balloons and forms from a
corrected characteristics file without reading the drawing again.

Web interface:

```
uvicorn src.webapp:app --port 8000
```

Set `OPENFAIR_TOKEN` to require an access token. Each run is stored in its own folder.

## Accuracy

Hand-made answer keys for the three NIST test drawings are in `eval/answer_keys/`
(45 required characteristics across 4 sheets, plus basic and reference dimensions
marked optional). Anyone can reproduce the score:

```
python -m eval.score --run                       # extract all three drawings, then score
python -m eval.score results.json eval/answer_keys/nist_ctc3.json   # score a saved run
```

A characteristic counts as found only when the GD&T type, tolerance values and datum
references all match (for dimensions: the quantity, nominal and tolerance values).
Results are written to `eval/results/<date>/score.json`. Model output can vary
slightly between runs, so report the date and model with any figure you quote.

Latest result, 26 Oct 2026, three full runs with the default model set in
`src/extraction/extract.py`:

| Run | Recall | Precision | F1 |
|---|---|---|---|
| 1 | 97.8% | 98.1% | 97.9% |
| 2 | 100% | 100% | 100% |
| 3 | 100% | 98.1% | 99.0% |
| All three | 99.3% (134 of 135) | 98.7% (155 of 157) | 99.0% |

The errors across those runs were one extra datum letter on a frame, one value read
that is not on the drawing, and one missed frame as a result of the extra datum.
Three public test drawings are a small sample: treat this as a check that the
pipeline works end to end, not as a guarantee for your drawings.

## Tests

```
pip install pytest
python -m pytest
```

The tests run offline (the vision model is replaced by a stub) and cover number
normalisation, duplicate merging, locating callouts on black and coloured drawings,
zone detection, multi-page drawings, the AS9102 workbook and the scorer.

## Data handling

Extraction sends rendered drawing images to the vision API. Customer drawings in
aerospace are often proprietary or export controlled (ITAR/EAR). Only process
drawings your organisation has approved for this, and keep private drawings in
`samples/private/` (ignored by git).

## Limitations

- Every value must be checked by the inspector before a FAIR is released. The tool
  prepares the paperwork; it does not replace verification.
- The model can still misread a symbol or miss a callout; run `eval.score` to see where.
- Form layout follows AS9102 Rev C field numbering. Check your customer's required revision.
- Zone grids are estimated when a drawing has no border labels.

## Roadmap

- STEP/QIF import for nominal coordinates and CMM program export
- Measured results import (CMM reports, height gauge exports) into Form 3

Test drawings are NIST MBE PMI test cases (public domain).
