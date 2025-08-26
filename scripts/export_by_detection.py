import os
import argparse

from typing import get_args

from utils.prompt import prompt_path, prompt_choices
from utils.exif import get_image_metadata
from utils.metadata import AvailableTags, AvailableDetections
from utils.files import allowed_image_exts, safe_copy

def export_by_detection(input_path: str, detection: AvailableDetections, output_path: str, dry_run: bool = False):
  copied = updated = skipped = 0
  
  for fn in os.listdir(input_path):
    src = os.path.join(input_path, fn)
    if not os.path.isfile(src):
      continue
    if os.path.splitext(fn)[1].lower() not in allowed_image_exts:
      continue
    
    if not get_image_metadata(src, "Detection") == detection:
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

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Export photos to a giving folder based on the detection tag.")
  parser.add_argument("--dry-run", help="Preview the export process without actually moving the files", action="store_true")
  args = parser.parse_args()
  
  input_path = prompt_path("Enter the input folder path: ").strip()
  detection = prompt_choices("Enter the targeted detection value: ", list(get_args(AvailableDetections)))
  output_path = prompt_path("Enter the output folder path: ").strip()
  
  export_by_detection(input_path, detection, output_path, args.dry_run)
  print("\n Your photos have been exported successfully.")