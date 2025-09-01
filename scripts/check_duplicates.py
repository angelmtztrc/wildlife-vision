#!/usr/bin/env python3
import os
import sys
import argparse
import re
import datetime as dt
import imagehash
import shutil
from typing import List, Tuple, Dict
from PIL import Image

from utils.prompt import prompt_path
from utils.files import allowed_image_exts


# ------- Config -------
DEFAULT_THRESHOLD = 5  # Hamming distance <= threshold => "duplicate"
# ----------------------

# Match: 20250803_221451__GF_Stream_Drink_Zone.jpg
DATETIME_RE = re.compile(r"^(?P<date>\d{8})_(?P<time>\d{6})__")

def is_image_file(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in allowed_image_exts

def parse_minute_from_filename(fname: str) -> dt.datetime | None:
    """
    Expect filenames like: YYYYMMDD_HHMMSS__Location[__...].ext
    Returns the datetime truncated to minute (seconds=0), or None if parsing fails.
    """
    m = DATETIME_RE.match(fname)
    if not m:
        return None
    date_str = m.group("date")   # e.g., 20250803
    time_str = m.group("time")   # e.g., 221451
    try:
        ts = dt.datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
        return ts.replace(second=0, microsecond=0)
    except Exception:
        return None

def group_by_minute(files: List[str]) -> Dict[dt.datetime, List[str]]:
    buckets: Dict[dt.datetime, List[str]] = {}
    for f in files:
        minute = parse_minute_from_filename(f)
        if minute is None:
            continue
        buckets.setdefault(minute, []).append(f)
    return buckets

def analyze_bucket(
    files: List[str],
    folder: str,
    threshold: int
) -> Tuple[List[str], List[str]]:
    """Return (kept, duplicates) for one minute bucket."""
    kept, dups, hashes = [], [], []
    for f in sorted(files):
        path = os.path.join(folder, f)
        try:
            with Image.open(path) as img:
                h = imagehash.phash(img)
        except Exception as e:
            print(f"[WARN] Skipping unreadable image {f}: {e}")
            continue

        if not hashes:
            kept.append(f)
            hashes.append(h)
            continue

        min_dist = min(abs(h - h2) for h2 in hashes)
        if min_dist <= threshold:
            dups.append(f)
        else:
            kept.append(f)
            hashes.append(h)
    return kept, dups

def ensure_output_dir(path: str):
    os.makedirs(path, exist_ok=True)

def copy_duplicates(dups: List[str], src_folder: str, dst_folder: str):
    ensure_output_dir(dst_folder)
    for f in dups:
        src = os.path.join(src_folder, f)
        dst = os.path.join(dst_folder, f)
        shutil.copy2(src, dst)

def main():
    input_path = prompt_path("Enter the input folder path: ").strip()
    output_path = prompt_path("Enter the output folder path (ignored if --dry-run): ").strip()
    parser = argparse.ArgumentParser(
        description="Detect near-duplicate trailcam images per minute and copy or list them."
    )

    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"Hamming distance threshold (<= is duplicate). Default: {DEFAULT_THRESHOLD}")
    parser.add_argument("--dry-run", action="store_true",
                        help="List duplicates and print summary (no files copied)")
    args = parser.parse_args()

    in_dir = os.path.abspath(input_path)
    out_dir = os.path.abspath(output_path)

    if not os.path.isdir(in_dir):
        print(f"[ERROR] Input folder does not exist: {in_dir}")
        sys.exit(1)

    files = [f for f in os.listdir(in_dir) if is_image_file(f)]
    total_images = len(files)

    buckets = group_by_minute(files)
    if not buckets:
        print("[INFO] No files matched expected filename pattern (YYYYMMDD__HHMMSS__...).")
        print(f"Total images scanned: {total_images}")
        sys.exit(0)

    total_kept, all_dups = 0, []

    for minute, flist in buckets.items():
        kept, dups = analyze_bucket(flist, in_dir, args.threshold)
        total_kept += len(kept)
        all_dups.extend(dups)

    if args.dry_run:
        print("=== Duplicate Analysis (Dry Run) ===\n")
        if all_dups:
            print("-- Duplicates Found --")
            for f in sorted(all_dups):
                print(f)
        else:
            print("No duplicates found.")
        print("\n=== Summary ===")
    else:
        if all_dups:
            print(f"Copying {len(all_dups)} duplicates to {out_dir} ...")
            copy_duplicates(all_dups, in_dir, out_dir)
            print("Done.")
        else:
            print("No duplicates to copy.")
        print("\n=== Summary ===")

    print(f"Input folder     : {in_dir}")
    print(f"Output folder    : {out_dir} ({'ignored in dry-run' if args.dry_run else 'received copies'})")
    print(f"Threshold        : {args.threshold}")
    print(f"Total images     : {total_images}")
    print(f"Kept images      : {total_kept}")
    print(f"Duplicates found : {len(all_dups)}")

if __name__ == "__main__":
    main()
