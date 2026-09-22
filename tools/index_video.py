"""Optional research utility; requires opencv-python, not a Council dependency.

Decode every frame and store only frame indices/timing/luminance-change statistics.
No images, audio, transcript or OCR output are exported.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('video', type=Path)
    parser.add_argument('--out', type=Path, required=True, help='New .csv.gz output file')
    args = parser.parse_args()
    if args.out.exists() or args.out.with_suffix('.meta.json').exists():
        parser.error('Output already exists; choose a new path')
    import cv2
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        parser.error('Cannot open video')
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        cap.release()
        parser.error('No valid frame rate; this utility requires a constant-rate source')
    width, height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    previous, count = None, 0
    try:
        with gzip.open(args.out, 'wt', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream, lineterminator='\n')
            writer.writerow(['frame_zero_based', 'time_seconds', 'mean_absolute_luma_change'])
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                delta = 0.0 if previous is None else cv2.mean(cv2.absdiff(gray, previous))[0]
                writer.writerow([count, f'{count / fps:.6f}', f'{delta:.6f}'])
                previous = gray
                count += 1
    finally:
        cap.release()
    sha = hashlib.sha256()
    with args.video.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(chunk)
    metadata = {'source_sha256': sha.hexdigest(), 'frames_decoded': count, 'fps': fps,
                'width': width, 'height': height, 'duration_seconds': count / fps,
                'method': 'Full-resolution BGR2GRAY; cv2.mean(absdiff(current, previous)); six-decimal CSV; first delta zero.',
                'visual_review': 'Separate timestamped contact-sheet/cut inspection; this ledger is computational, not a transcript.'}
    args.out.with_suffix('.meta.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
