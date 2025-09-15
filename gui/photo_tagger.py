import os
import re
import argparse
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageFile
from typing import Literal

ImageFile.LOAD_TRUNCATED_IMAGES = True

from scripts.utils.prompt import prompt_path
from scripts.utils.exif import set_image_metadata, get_image_metadata
from scripts.utils.files import allowed_image_exts
from scripts.utils.metadata import AvailableDetections

DEFAULT_MAX_IMAGES_PER_SESSION = 500
STRIP_DET_SUFFIX_RE = re.compile(r"(?:__)(EMPTY|ANIMAL|OBJECT)$", re.IGNORECASE)

def has_detection_suffix(name_no_ext: str) -> bool:
    return STRIP_DET_SUFFIX_RE.search(name_no_ext) is not None

def strip_detection_suffix(name_no_ext: str) -> str:
    return STRIP_DET_SUFFIX_RE.sub("", name_no_ext)

class PhotoTagger: 
  def __init__(self, root, folder, no_tagged_only):
    self.root = root
    self.folder = folder
    self.index = 0
    
    self.root.attributes("-fullscreen", True)
    self.screen_w = self.root.winfo_screenwidth()
    self.screen_h = self.root.winfo_screenheight()
    self.max_w = int(self.screen_w * 0.8)
    self.max_h = int(self.screen_h * 0.8)
    
    images = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in allowed_image_exts]
    
    if no_tagged_only:
      untagged = []
      for f in images:
        stem, _ = os.path.splitext(f)
        if has_detection_suffix(stem):
          continue
        detection = get_image_metadata(os.path.join(folder, f), "Detection")
        if not detection:
          untagged.append(f)
      images = untagged

    images.sort(reverse=True)  

    if len(images) > DEFAULT_MAX_IMAGES_PER_SESSION:      
      images = images[:DEFAULT_MAX_IMAGES_PER_SESSION]
    
    
    self.images = images
    
    self.label = tk.Label(root, text="", font=("Arial", 18))
    self.label.pack()
    
    self.canvas = tk.Canvas(root, bg="black")
    self.canvas.pack(fill=tk.BOTH, expand=True)
    
    if not self.images:
      self.label.config(text="No images to tag in this folder.")
    else:
      self.load_image()
    
    
    root.bind("1", lambda e: self.set_label("empty"))
    root.bind("2", lambda e: self.set_label("animal"))
    root.bind("3", lambda e: self.set_label("object"))
    root.bind("4", lambda e: self.set_label("irrelevant"))
    
    root.bind("<Right>", lambda e: self.next_image())
    root.bind("<Left>", lambda e: self.prev_image())
    
    root.bind("<Escape>", lambda e: self.root.destroy())
    
    help_text = "Keys: [1]=empty  [2]=animal  [3]=object  [4]=irrelevant  ←/→ navigate   Esc exit"
    self.root.title(f"Photo Tagger — {help_text}")
    
  def load_image(self):
    img_path = os.path.join(self.folder, self.images[self.index])
    
    detection = get_image_metadata(img_path, "Detection")
    img = Image.open(img_path)

    # Resize to fit canvas
    img.thumbnail((self.max_w, self.max_h), Image.Resampling.LANCZOS)
    self.tk_img = ImageTk.PhotoImage(img)

    self.canvas.delete("all")
    x = (self.screen_w - img.width) // 2
    y = (self.screen_h - img.height) // 2
    self.canvas.create_image(x, y, anchor=tk.NW, image=self.tk_img)
    
    self.label.config(text=f"{self.images[self.index]} ({self.index+1}/{len(self.images)}) - Detection: {detection if detection else "none"}" )

  def set_label(self, label_value: AvailableDetections):
    received_name = self.images[self.index]
    received_path = os.path.join(self.folder, self.images[self.index])
    
    try: 
      set_image_metadata(received_path, "Detection", label_value)
    except Exception as e:
      print(f"[ERROR] Failed to set metadata for {received_path}: {e}")  
    
    suffix = label_value.upper()
    stem, ext = os.path.splitext(received_name)
    clean_stem = strip_detection_suffix(stem)
    new_name = f"{clean_stem}__{suffix}{ext}"
    new_path = os.path.join(self.folder, new_name)
    
    try:
      os.rename(received_path, new_path)
      final_name = new_name
    except Exception as e:
      print(f"[ERROR] Failed to rename {received_path} to {new_path}: {e}")
      self.next_image()
      return
    
    self.images[self.index] = final_name
    self.next_image()

  def next_image(self):
    if self.index < len(self.images) - 1:
        self.index += 1
        self.load_image()
    else: 
      self.label.config(text=f"Done! ({len(self.images)} processed)")

  def prev_image(self):
    if self.index > 0:
        self.index -= 1
        self.load_image()


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--no-tagged-only", help="Only display untagged photos", action="store_true")
  args = parser.parse_args()
  
  root = tk.Tk()
  root.title("Photo Tagger")
  
  input_path = prompt_path("Enter the input folder path: ").strip()

  if input_path:
    app = PhotoTagger(root, input_path, args.no_tagged_only)
    root.mainloop()