"""Snap vision-estimated bboxes to blue annotation clusters found with OpenCV."""
import json
import sys
from pathlib import Path

import cv2
import numpy as np


def find_blue_clusters(image_path: str, debug: bool = True) -> list[tuple[int, int, int, int]]:
    img = cv2.imread(image_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # blue annotations: hue ~120 in OpenCV's 0-179 scale
    mask = cv2.inRange(hsv, np.array([100, 80, 80]), np.array([140, 255, 255]))
    # fuse characters of one callout into a single blob
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
    fused = cv2.dilate(mask, kernel)
    n, _, stats, _ = cv2.connectedComponentsWithStats(fused)
    clusters = []
    for i in range(1, n):  # 0 is background
        x, y, w, h, area = stats[i]
        if area < 800:  # ignore specks
            continue
        clusters.append((int(x), int(y), int(w), int(h)))
    if debug:
        dbg = img.copy()
        for (x, y, w, h) in clusters:
            cv2.rectangle(dbg, (x, y), (x + w, y + h), (0, 0, 255), 3)
        out = str(Path(image_path).with_name(Path(image_path).stem + "_clusters.png"))
        cv2.imwrite(out, dbg)
        print(f"{len(clusters)} blue clusters found, debug image: {out}")
    return clusters


def snap(image_path: str, json_path: str) -> None:
    clusters = find_blue_clusters(image_path)
    entries = json.loads(Path(json_path).read_text(encoding="utf-8"))
    for e in entries:
        bbox = e.get("bbox")
        if not bbox:
            continue
        cx, cy = bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2
        best = min(clusters, key=lambda c: (c[0] + c[2] / 2 - cx) ** 2
                                           + (c[1] + c[3] / 2 - cy) ** 2)
        e["bbox"] = list(best)
        e["bbox_source"] = "opencv-blue"
    Path(json_path).write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                               encoding="utf-8")
    print(f"Snapped {len(entries)} entries to blue clusters")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: py -m src.ballooning.snap <image_path> <extracted_json>")
        sys.exit(1)
    snap(sys.argv[1], sys.argv[2])
