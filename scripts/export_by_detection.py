#!/usr/bin/env python3
import os
import argparse
import re
from typing import get_args

from utils.prompt import prompt_path, prompt_choices
from utils.metadata import AvailableDetections
from utils.files import allowed_image_exts, safe_copy

# Regex to capture detection suffix from filename
# Example: 20250803_221451__GF_Stream_Drink_Zone__ANIMAL.jpg
FILENAME_RE = re.compile(
    r"^(?P<date>\d{8})_(?P<time>\d{6})__(?P<location>.+?)__(?P<det>[A-Za-z]+)$"
)

def get_detection_from_filename(filename: str) -> str | None:
    """Extract detection (uppercased) from filename, or None if not valid."""
    stem, _ = os.path.splitext(filename)
    m = FILENAME_RE.match(stem)
    if not m:
        return None
    det = m.group("det").lower()
    if det in get_args(AvailableDetections):
        return det
    return None

def export_by_detection(input_path: str, detection: AvailableDetections, output_path: str, dry_run: bool = False):
    copied = updated = skipped = 0
    
    for fn in os.listdir(input_path):
        src = os.path.join(input_path, fn)
        if not os.path.isfile(src):
            continue
        if os.path.splitext(fn)[1].lower() not in allowed_image_exts:
            continue

        det = get_detection_from_filename(fn)
        if det != detection:
            skipped += 1
            continue

        dst = os.path.join(output_path, fn)
        if dry_run:
            print(f"Would copy {src} to {dst}")
        else:
            existed = os.path.exists(dst)
            safe_copy(src, dst)
            if existed:
                updated += 1
            else:
                copied += 1
      
    print(f"\nDone. new: {copied}, replaced: {updated}, skipped: {skipped}")

def main():
    parser = argparse.ArgumentParser(
      description="Export photos to a given folder based on the detection in filename."
    )
    parser.add_argument(
      "--dry-run",
      help="Preview the export process without actually copying the files",
      action="store_true",
    )
    args = parser.parse_args()
    
    input_path = prompt_path("Enter the input folder path: ").strip()
    detection = prompt_choices("Enter the targeted detection value: ", list(get_args(AvailableDetections)))
    output_path = prompt_path("Enter the output folder path: ").strip()
    
    export_by_detection(input_path, detection, output_path, args.dry_run)
    print("\nYour photos have been exported successfully.")

if __name__ == "__main__":
  main()