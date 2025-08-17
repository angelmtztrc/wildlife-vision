import os
import shutil
from pathlib import Path

from utils.prompt import prompt_path
from utils.files import allowed_image_exts
from utils.exif import get_image_metadata

def detection_organiser(input_path, output_path):
  input_path = Path(input_path).resolve()
  if not os.path.exists(output_path):
    os.makedirs(output_path)
  
  detection_categories = ["empty", "animal", "object"]
  for category in detection_categories:
    os.makedirs(os.path.join(output_path, category), exist_ok=True)
  
  for file in input_path.iterdir():
    if file.suffix in allowed_image_exts:
      detection = get_image_metadata(file, "Detection")
      if detection:
        category = detection.lower()
        new_folder = os.path.join(output_path, category)
        shutil.move(str(file), os.path.join(new_folder, file.name))
        print(f"File moved: {file.name} → {new_folder}")

if __name__ == "__main__":
  input_path = prompt_path("Enter the input folder path: ").strip()
  output_path = prompt_path("Enter the output folder path: ").strip()
  
  detection_organiser(input_path, output_path)
  print("\n Your photos have been organised successfully.")