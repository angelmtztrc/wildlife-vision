from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk, ImageFile

from wv.gui.detection_triage.controller import DetectionTriageController

ImageFile.LOAD_TRUNCATED_IMAGES = True


class DetectionTriageApp:
    def __init__(self, input_path: Path):
        self.root = tk.Tk()
        self.root.title("Detection Triage")
        self.root.attributes("-fullscreen", True)

        self.controller = DetectionTriageController(input_path)
        self.controller.on_change_side_effect = self._refresh
        self.controller.on_complete_side_effect = self._on_complete

        self._current_photo: ImageTk.PhotoImage | None = None
        self._setup_ui()
        self._setup_bindings()
        self._refresh()

    def _setup_ui(self):
        header = ttk.Frame(self.root, padding=10)
        header.pack(fill=tk.X)

        self.progress_label = ttk.Label(header, font=("Menlo", 16))
        self.progress_label.pack(side=tk.LEFT)

        self.filename_label = ttk.Label(header, font=("Menlo", 14))
        self.filename_label.pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(self.root, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack()

        self.helper_label = ttk.Label(
            bottom_frame,
            text="[1]=empty  [2]=animal  [3]=irrelevant  [←/→] navigate   [Esc] exit",
            font=("Menlo", 12),
        )

        self.helper_label.pack()

    def _setup_bindings(self):
        self.root.bind("1", lambda e: self.controller.set_tag("empty"))
        self.root.bind("2", lambda e: self.controller.set_tag("animal"))
        self.root.bind("3", lambda e: self.controller.set_tag("irrelevant"))
        self.root.bind("<Left>", lambda e: self.controller.previous_image())
        self.root.bind("<Right>", lambda e: self.controller.next_image())
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def _refresh(self):
        state = self.controller.state
        self.progress_label.config(text=f"{state.index + 1}/{state.total_images}")

        current_file = state.current_image
        if current_file:
            self.filename_label.config(text=current_file.name)
            self._load_image(current_file)

    def _load_image(self, image_path: Path):
        try:
            img = Image.open(image_path)
            img.thumbnail(
                (
                    self.root.winfo_screenwidth() * 0.8,
                    self.root.winfo_screenheight() * 0.8,
                ),
                Image.Resampling.LANCZOS,
            )
            self._current_photo = ImageTk.PhotoImage(img)

            self.canvas.delete("all")
            self.canvas.update_idletasks()
            x = (self.canvas.winfo_width() - self._current_photo.width()) // 2
            y = (self.canvas.winfo_height() - self._current_photo.height()) // 2
            self.canvas.create_image(x, y, anchor=tk.NW, image=self._current_photo)

        except Exception as e:
            pass

    def _on_complete(self):
        messagebox.showinfo(
            "Done!", f"{len(self.controller.state.total_images)} images processed."
        )
        self._quit()

    def _quit(self):
        if not self.controller.state.is_completed:
            if not messagebox.askyesno(
                "Quit?",
                "You have not completed triaging all images. Are you sure you want to exit?",
            ):
                return

        self.root.quit()

    def run(self):
        self.root.mainloop()
