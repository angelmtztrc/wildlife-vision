import os
import piexif
from datetime import datetime
from PIL import Image, ExifTags

from metadata import AvailableTags

def get_datetime_from_image(img_path):
  try: 
    image = Image.open(img_path)
    exif_data = image._getexif()
    if exif_data:
      for tag, value in exif_data.items():
        decoded_tag = ExifTags.TAGS.get(tag)
        if decoded_tag == "DateTimeOriginal":
          return datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
  except Exception as e:
    print(f"Could not read EXIF for {img_path}: {e}")
    pass 
    
  ts = os.path.getmtime(img_path)
  return datetime.fromtimestamp(ts)

def get_image_metadata(img_path, tag_name: AvailableTags):
  try:
    with Image.open(img_path) as img:
      exif = img._getexif()
      if not exif:
        return ""
      
      for metadata, value in exif.items():
        decoded_tag = ExifTags.TAGS.get(metadata)
        if decoded_tag == "ImageDescription":
          description = value
        
      if not description:
        return ""
      
      pairs = dict(part.split("=") for part in description.split(";") if "=" in part)
      
      return pairs.get(tag_name, "")
  except Exception as e:
    print(f"Error reading metadata from {img_path}: {e}")
    return ""

def set_image_metadata(img_path, tag_name: AvailableTags, tag_value):
  img = Image.open(img_path)
  
  try:
    exif_bytes = img.info.get("exif", None)
    if exif_bytes:
        exif_dict = piexif.load(exif_bytes)
    else:
        # Minimal EXIF dict
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
  except Exception as e:
    print(f"[WARN] Could not read EXIF from {img_path}: {e}")
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    
  description_bytes = exif_dict["0th"].get(piexif.ImageIFD.ImageDescription, b"")
  
  try:
    description_str = description_bytes.decode("utf-8").strip()
  except Exception:
    description_str = ""
  
  existing_tags = {}
  if description_str:
    for item in description_str.split(";"):
      if "=" in item:
        key, value = item.split("=", 1)
        existing_tags[key.strip()] = value.strip()
  
  existing_tags[tag_name] = tag_value
  
  updated_description_str = ";".join([f"{key}={value}" for key, value in existing_tags.items()])
  
  exif_dict["0th"][piexif.ImageIFD.ImageDescription] = updated_description_str.encode("utf-8")
  
  exif_bytes = piexif.dump(exif_dict)
  img.save(img_path, exif=exif_bytes)

  print(f"Setting {tag_name} to {tag_value} for {img_path} was completed successfully.")