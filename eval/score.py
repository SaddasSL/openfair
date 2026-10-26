"""Score extraction results against hand-made answer keys.

Score saved results (no API key needed):
    python -m eval.score output/nist_ctc3_characteristics.json eval/answer_keys/nist_ctc3.json

Run the full benchmark (extracts all three NIST drawings, needs ANTHROPIC_API_KEY):
    python -m eval.score --run

A characteristic counts as found when its identity matches the key:
  * GD&T: same characteristic (position, flatness ...), same tolerance numbers,
    same datum references in the same order
  * dimensions: the same set of numbers in value and tolerance (so ".438" = "0.438",
    and "4X Ø.625 ±.005" must carry the 4, the .625 and the .005)
Recall is measured on required characteristics. Basic and reference dimensions
are optional: finding them is not penalised, missing them is not counted.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from src import normalize

ROOT = Path(__file__).resolve().parents[1]
KEYS = ROOT / "eval" / "answer_keys"
DRAWINGS = ["nist_ctc3", "nist_ctc4", "nist_ctc5"]


def load_entries(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = data["characteristics"] if isinstance(data, dict) else data
    return [e for e in entries if e.get("type") != "note"]


def score(found: list[dict], key: dict) -> dict:
    expected = key["characteristics"]
    unmatched = list(range(len(found)))
    matches, missed = [], []
    for k in expected:
        sig = normalize.signature(k)
        hit = next((i for i in unmatched
                    if normalize.signature(found[i]) == sig
                    and found[i].get("page", k.get("page", 1)) == k.get("page", 1)), None)
        if hit is None:
            if k["kind"] == "required":
                missed.append(k)
        else:
            unmatched.remove(hit)
            matches.append((k, found[hit]))
    required = sum(k["kind"] == "required" for k in expected)
    found_required = sum(k["kind"] == "required" for k, _ in matches)
    extra = [found[i] for i in unmatched]
    precision = len(matches) / len(found) if found else 0.0
    recall = found_required / required if required else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"required": required, "found_required": found_required, "extracted": len(found),
            "matched": len(matches), "recall": recall, "precision": precision, "f1": f1,
            "missed": missed, "extra": extra}


def report(name: str, s: dict, verbose: bool = True) -> None:
    print(f"\n{name}: recall {s['recall']:.1%} ({s['found_required']}/{s['required']} required), "
          f"precision {s['precision']:.1%} ({s['matched']}/{s['extracted']} extracted), F1 {s['f1']:.1%}")
    if verbose:
        for k in s["missed"]:
            print(f"   missed: [{k['type']}] {k['value']} {k.get('tolerance') or ''}")
        for e in s["extra"]:
            print(f"   extra:  [{e.get('type')}] {e.get('value')} {e.get('tolerance') or ''}")


def run_benchmark(out_dir: Path) -> dict:
    from src.pipeline import run_pipeline
    results = {}
    for name in DRAWINGS:
        res = run_pipeline(str(ROOT / "samples" / "public" / f"{name}.pdf"), out_dir=str(out_dir))
        results[name] = res["json"]
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="?", help="characteristics JSON to score")
    ap.add_argument("key", nargs="?", help="answer key JSON")
    ap.add_argument("--run", action="store_true", help="extract all NIST drawings, then score")
    ap.add_argument("--out", default="eval/results", help="where --run writes its outputs")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    if a.run:
        out = Path(a.out) / date.today().isoformat()
        files = run_benchmark(out)
        pairs = [(n, files[n], KEYS / f"{n}.json") for n in DRAWINGS]
    elif a.results and a.key:
        pairs = [(Path(a.results).stem, a.results, a.key)]
    else:
        ap.print_help()
        return 2

    totals = {"required": 0, "found_required": 0, "extracted": 0, "matched": 0}
    summary = {}
    for name, res_path, key_path in pairs:
        s = score(load_entries(res_path), json.loads(Path(key_path).read_text(encoding="utf-8")))
        report(name, s, not a.quiet)
        for k in totals:
            totals[k] += s[k]
        summary[name] = {k: s[k] for k in ("required", "found_required", "extracted", "matched", "recall", "precision", "f1")}
    if len(pairs) > 1:
        r = totals["found_required"] / totals["required"]
        p = totals["matched"] / totals["extracted"] if totals["extracted"] else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        print(f"\nOVERALL: recall {r:.1%}, precision {p:.1%}, F1 {f:.1%}")
        summary["overall"] = {**totals, "recall": r, "precision": p, "f1": f}
    if a.run:
        (Path(a.out) / date.today().isoformat() / "score.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
