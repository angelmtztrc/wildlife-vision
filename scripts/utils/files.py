import os
import shutil

allowed_image_exts = {".jpg", ".jpeg", ".png", ".heic", ".JPG", ".JPEG", ".PNG"}

def safe_copy(path: str, output_path: str):
  """
    Copy a file (preserving metadata) to output_path safely.
    - Creates parent folders if needed.
    - Writes to a temporary file first.
    - Atomically replaces the destination file.
  """
  os.makedirs(os.path.dirname(output_path), exist_ok=True)
  tmp = output_path + ".tmpcopy"
  shutil.copy2(path, tmp) 
  os.replace(tmp, output_path) 