import os
import argparse
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk

from scripts.utils.exif import set_image_metadata, get_image_metadata
from scripts.utils.files import allowed_image_exts

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
      images = [f for f in images if not get_image_metadata(os.path.join(folder, f), "Detection")]
    else: self.images = images
    
    self.label = tk.Label(root, text="", font=("Arial", 18))
    self.label.pack()
    
    self.canvas = tk.Canvas(root, bg="black")
    self.canvas.pack(fill=tk.BOTH, expand=True)
    
    self.load_image()
    
    
    root.bind("1", lambda e: self.set_label("empty"))
    root.bind("2", lambda e: self.set_label("animal"))
    root.bind("3", lambda e: self.set_label("object"))
    
    root.bind("<Right>", lambda e: self.next_image())
    root.bind("<Left>", lambda e: self.prev_image())
    
    root.bind("<Escape>", lambda e: self.root.destroy())
    
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

  def set_label(self, label_value):
    img_path = os.path.join(self.folder, self.images[self.index])
    set_image_metadata(img_path, "Detection", label_value)
    self.next_image()

  def next_image(self):
    if self.index < len(self.images) - 1:
        self.index += 1
        self.load_image()

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
  
  folder = filedialog.askdirectory(title="Select a folder")
  if folder:
    app = PhotoTagger(root, folder, args.no_tagged_only)
    root.mainloop()