#!/usr/bin/env python3
import os
import sys
import argparse
import re
from typing import Optional
from typing import get_args

from utils.prompt import prompt_path
from utils.exif import get_image_metadata
from utils.files import allowed_image_exts
from utils.metadata import AvailableDetections

# Build once from your Literal
ALLOWED_DETECTIONS = set(get_args(AvailableDetections))  # {"empty","animal","object"}

# Regex: YYYYMMDD_HHMMSS__Location[__Detection].ext
FILENAME_RE = re.compile(
    r"^(?P<date>\d{8})_(?P<time>\d{6})__(?P<location>[^.]+?)(?:__(?P<det>[A-Za-z]+))?$"
)

def is_image_file(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in allowed_image_exts

def parse_base_parts(fname: str) -> Optional[tuple[str, str, str]]:
    """
    Parse filename into (date, time, location) while stripping any existing detection suffix.
    Example:
      20250803_221451__GF_Stream_Drink_Zone__ANIMAL.jpg
        -> (20250803, 221451, GF_Stream_Drink_Zone)
    """
    name_no_ext, _ = os.path.splitext(fname)
    m = FILENAME_RE.match(name_no_ext)
    if not m:
        return None

    date, time, location, det = m.group("date"), m.group("time"), m.group("location"), m.group("det")

    # If suffix looks like a detection, strip it
    if det and det.lower() in ALLOWED_DETECTIONS:
        return date, time, location
    return (date, time, location) if location else None

def rename_with_detection(folder: str, dry_run: bool = True):
    files = []
    with os.scandir(folder) as it:
        for entry in it:
            if entry.is_file() and is_image_file(entry.name):
                files.append(entry.name)

    total_considered, renamed, skipped, already_ok = 0, 0, 0, 0

    for f in files:
        path = os.path.join(folder, f)
        base_parts = parse_base_parts(f)
        if not base_parts:
            print(f"[WARN] Skipping file with unexpected name: {f}")
            skipped += 1
            continue

        date, time, location = base_parts

        # Read detection from metadata
        detection_raw = get_image_metadata(path, "Detection")
        if not detection_raw:
            print(f"[WARN] No Detection tag found, skipping: {f}")
            skipped += 1
            continue

        detection_lc = str(detection_raw).strip().lower()
        if detection_lc not in ALLOWED_DETECTIONS:
            print(f"[WARN] Invalid detection value '{detection_raw}' in {f}, skipping")
            skipped += 1
            continue

        detection_up = detection_lc.upper()
        ext = os.path.splitext(f)[1].lower()
        new_name = f"{date}_{time}__{location}__{detection_up}{ext}"
        new_path = os.path.join(folder, new_name)

        total_considered += 1
        if f == new_name:
            already_ok += 1
            continue  # already correct

        if dry_run:
            print(f"[DRY] {f} -> {new_name}")
        else:
            os.rename(path, new_path)
            print(f"[OK]  {f} -> {new_name}")
            renamed += 1

    print("\n=== Summary ===")
    print(f"Folder                        : {os.path.abspath(folder)}")
    print(f"Total images scanned          : {len(files)}")
    print(f"Considered (valid Detection)  : {total_considered}")
    print(f"Already correct               : {already_ok}")
    print(f"Renamed                       : {renamed if not dry_run else (total_considered - already_ok)}")
    print(f"Skipped                       : {skipped}")
    if dry_run:
        print("NOTE: Run again without --dry-run to actually rename.")

def main():
    parser = argparse.ArgumentParser(
        description="Rename images with Detection value in format: YYYYMMDD_HHMMSS__Location__DETECTION"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview renames without applying")
    args = parser.parse_args()

    input_path = prompt_path("Enter the input folder path: ").strip()
    folder = os.path.abspath(input_path)
    if not os.path.isdir(folder):
        print(f"[ERROR] Folder does not exist: {folder}")
        sys.exit(1)

    rename_with_detection(folder, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
