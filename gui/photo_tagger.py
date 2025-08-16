import os
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk

from scripts.utils.exif import set_image_metadata, get_image_metadata
from scripts.utils.files import allowed_image_exts

class PhotoTagger: 
  def __init__(self, root, folder):
    self.root = root
    self.folder = folder
    self.images = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in allowed_image_exts]
    self.index = 0
    
    self.label = tk.Label(root, text="", font=("Arial", 18))
    self.label.pack()
    
    self.canvas = tk.Canvas(root, width=800, height=600)
    self.canvas.pack()
    
    self.load_image()
    
    
    root.bind("1", lambda e: self.set_label("empty"))
    root.bind("2", lambda e: self.set_label("animal"))
    root.bind("3", lambda e: self.set_label("object"))
    
    root.bind("<Right>", lambda e: self.next_image())
    root.bind("<Left>", lambda e: self.prev_image())
    
  def load_image(self):
    img_path = os.path.join(self.folder, self.images[self.index])
    
    detection = get_image_metadata(img_path, "Detection")
    img = Image.open(img_path)

    # Resize to fit canvas
    img.thumbnail((800, 600))
    self.tk_img = ImageTk.PhotoImage(img)

    self.canvas.delete("all")
    self.canvas.create_image(400, 300, image=self.tk_img)
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
  root = tk.Tk()
  root.title("Photo Tagger")
  
  folder = filedialog.askdirectory(title="Select a folder")
  if folder:
    app = PhotoTagger(root, folder)
    root.mainloop()