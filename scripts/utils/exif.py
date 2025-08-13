import os
import piexif
from datetime import datetime
from PIL import Image, ExifTags

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

def set_image_metadata(img_path, tag_name, tag_value):
  return None