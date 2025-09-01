#!/usr/bin/env python3
import argparse
import os
import sys
import shutil
from dataclasses import dataclass
from typing import Iterable

from PIL import Image, ImageStat, ImageFile

from utils.files import allowed_image_exts
from utils.prompt import prompt_path

# Allow reading slightly corrupted/truncated images (common on trail cams)
ImageFile.LOAD_TRUNCATED_IMAGES = True

@dataclass
class ImageMetrics:
    mean: float
    stddev: float
    pct_high: float  # fraction of pixels above high_level (0..1)
    path: str

def is_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in allowed_image_exts

def iter_images(folder: str) -> Iterable[str]:
    for name in os.listdir(folder):
        p = os.path.join(folder, name)
        if os.path.isfile(p) and is_image(p):
            yield p

def compute_metrics(path: str, high_level: int = 240) -> ImageMetrics:
    with Image.open(path) as im:
        g = im.convert("L")
        st = ImageStat.Stat(g)
        mean = float(st.mean[0])
        stddev = float(st.stddev[0])

        hist = g.histogram()
        total = sum(hist)
        high_count = sum(hist[high_level:]) if 0 <= high_level <= 255 else 0
        pct_high = (high_count / total) if total > 0 else 0.0

    return ImageMetrics(mean=mean, stddev=stddev, pct_high=pct_high, path=path)

def is_overexposed(m: ImageMetrics, mean_threshold: float, std_threshold: float, pct_high_threshold: float) -> bool:
    rule_a = (m.mean >= mean_threshold and m.stddev <= std_threshold)
    rule_b = (m.pct_high >= pct_high_threshold)
    return rule_a or rule_b

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def format_pct(x: float) -> str:
    return f"{x*100:.1f}%"

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Detect and COPY likely overexposed IR/night photos for review."
    )
    
    p.add_argument("--dry-run", action="store_true", default=False,  help="Only list flagged images, do not copy.")
    p.add_argument("--mean-threshold", type=float, default=200.0, help="Grayscale mean threshold (default: 200).")
    p.add_argument("--std-threshold", type=float, default=25.0, help="Grayscale stddev threshold (default: 25).")
    p.add_argument("--high-level", type=int, default=240, help="Gray level considered 'near white' (default: 240).")
    p.add_argument("--pct-high-threshold", type=float, default=0.60, help="Fraction of near-white pixels to flag (0..1, default: 0.60).")
    return p.parse_args()

def main():
    args = parse_args()

    input_path = prompt_path("Enter the input folder path: ").strip()
    output_path = prompt_path("Enter the output folder path (ignored if --dry-run): ").strip()
    

    if not os.path.isdir(input_path):
        print(f"ERROR: input_dir does not exist or is not a directory: {input_path}", file=sys.stderr)
        sys.exit(2)

    total = 0
    flagged = 0
    errors = 0

    print("Scanning images...")
    for path in iter_images(input_path):
        total += 1
        try:
            m = compute_metrics(path, high_level=args.high_level)
            if is_overexposed(
                m,
                mean_threshold=args.mean_threshold,
                std_threshold=args.std_threshold,
                pct_high_threshold=args.pct_high_threshold
            ):
                flagged += 1
                print(
                    f"[FLAG] {path}\n"
                    f"       mean={m.mean:.1f}  std={m.stddev:.1f}  pct_high={format_pct(m.pct_high)}"
                )

                if not args.dry_run:
                    rel = os.path.basename(path)
                    out_path = os.path.join(output_path, rel)
                    ensure_dir(output_path)
                    shutil.copy2(path, out_path)
        except Exception as e:
            errors += 1
            print(f"[ERR]  {path} -> {e}")

    print("\n=== Summary ===")
    print(f"Analyzed images : {total}")
    print(f"Flagged         : {flagged}")
    print(f"Errors          : {errors}")
    if args.dry_run:
        print("Mode            : DRY RUN (no files copied)")
    else:
        print("Mode            : EXECUTE (flagged files were copied)")
        print(f"Output dir      : {output_path}")

if __name__ == "__main__":
    main()
