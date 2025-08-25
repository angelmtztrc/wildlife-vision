import shutil
import argparse
from pathlib import Path

from utils.files import allowed_image_exts
from utils.exif import get_datetime_from_image, set_image_metadata
from utils.prompt import prompt, prompt_path

def organise_photos(input_path, camera_location, generate_subfolders, output_path): 
  input_path = Path(input_path).resolve()
  output_path = Path(output_path)
  
  if not input_path.exists():
    print(f"Input path does not exist: {input_path}")
    return

  print("Organising photos...")
  for file in input_path.iterdir():
    if file.suffix in allowed_image_exts:
      date_taken = get_datetime_from_image(file)
      date_str = date_taken.strftime("%Y%m%d")
      time_str = date_taken.strftime("%H%M%S")
      
      date_folder = output_path / date_str
      
      if generate_subfolders:
        date_folder.mkdir(parents=True, exist_ok=True) 
      
      new_filename = f"{date_str}_{time_str}__{camera_location}{file.suffix.lower()}"
      new_file_path = date_folder / new_filename if generate_subfolders else output_path / new_filename
      
      shutil.move(str(file), new_file_path)
      set_image_metadata(new_file_path, "Location", camera_location)
      print(f"File moved: {file.name} → {new_file_path}")

if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--generate-subfolders", help="Allow to generate YYYYMMDD subfolders", action="store_true")
  
  args = parser.parse_args()
  
  input_path = prompt_path("Enter the input folder path: ").strip()
  camera_location = prompt("Enter the location of the camera: ").strip().replace(" ", "_")
  output_path = prompt_path("Enter the output folder path: ").strip()
  
  organise_photos(input_path, camera_location, args.generate_subfolders, output_path)
  print("\n Your photos have been organised successfully.")