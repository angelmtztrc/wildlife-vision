import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageOps, ImageTk

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.gui.review_detection_preview.bindings import register_bindings
from wv.gui.review_detection_preview.controller import LABEL_ORDER, LABEL_SHORTCUTS, ReviewDetectionPreviewController, build_controller
from wv.gui.review_detection_preview.thumbnails import ThumbnailLoader
from wv.use_cases.session.review_detection_apply import ApplyReviewDetectionResult
from wv.use_cases.session.review_detection_preview_load import LoadReviewDetectionPreviewInput, ReviewDetectionPreviewItem, run as load_preview

logger = get_logger(__name__)
BACKGROUND = "#1b1b1b"
PANEL = "#252525"
CARD = "#2b2b2b"
BORDER = "#555555"
FOCUS = "#4c9aff"
ACTIVE = "#1d5fa7"
TEXT = "#f5f5f5"
MUTED_TEXT = "#c8c8c8"
CARD_GUTTER = 6
CARD_DETAILS_HEIGHT = 72
ROW_GUTTER = 12


class FlatButton(tk.Label):
    """Focusable rectangular control with consistent preview styling."""

    def __init__(self, parent, text, command, *, active=False, **kwargs):
        self.command = command
        self.active = active
        super().__init__(
            parent,
            text=text,
            bg=ACTIVE if active else PANEL,
            fg=TEXT,
            padx=10,
            pady=8,
            cursor="hand2",
            takefocus=True,
            highlightthickness=1,
            highlightbackground=FOCUS if active else BORDER,
            highlightcolor=FOCUS,
            **kwargs,
        )
        self.bind("<Button-1>", self._activate)
        self.bind("<Return>", self._activate)
        self.bind("<space>", self._activate)
        self.bind("<Enter>", self._hover)
        self.bind("<Leave>", self._leave)
        self.bind("<FocusIn>", self._focus_in)
        self.bind("<FocusOut>", self._focus_out)

    def configure_state(self, *, text: str, active: bool = False) -> None:
        self.active = active
        self.configure(
            text=text,
            bg=ACTIVE if active else PANEL,
            highlightbackground=FOCUS if active else BORDER,
        )

    def _activate(self, event):
        self.command()
        return "break"

    def _hover(self, event):
        if not self.active:
            self.configure(bg="#353535")

    def _leave(self, event):
        if not self.active:
            self.configure(bg=PANEL)

    def _focus_in(self, event):
        self.configure(highlightthickness=2)

    def _focus_out(self, event):
        self.configure(highlightthickness=1)


class VirtualGrid:
    """Canvas grid that creates drawing objects only for visible rows."""

    def __init__(self, parent, on_focus, on_open, on_visible):
        self.canvas = tk.Canvas(parent, bg=BACKGROUND, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(parent, orient="vertical", command=self._scroll)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.bind("<Configure>", lambda event: self.render(force=True))
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda event: self._scroll_units(-3))
        self.canvas.bind("<Button-5>", lambda event: self._scroll_units(3))
        self.items: list[ReviewDetectionPreviewItem] = []
        self.items_by_id: dict[str, ReviewDetectionPreviewItem] = {}
        self.focused_id: str | None = None
        self.staged_label_for = lambda item: None
        self.photos: dict[str, ImageTk.PhotoImage] = {}
        self.drawn: dict[str, tuple[int, ...]] = {}
        self.on_focus = on_focus
        self.on_open = on_open
        self.on_visible = on_visible

    def set_items(self, items, focused_id, staged_label_for):
        self.items = items
        self.items_by_id = {item.image_id: item for item in items}
        self.focused_id = focused_id
        self.staged_label_for = staged_label_for
        self.canvas.yview_moveto(0)
        self.render(force=True)

    def set_focus(self, image_id: str | None) -> None:
        old_id = self.focused_id
        self.focused_id = image_id
        for item_id in (old_id, image_id):
            if item_id in self.drawn:
                self._style(item_id)

    def ensure_visible(self, index: int | None) -> None:
        if index is None:
            return
        top = self.canvas.canvasy(0)
        bottom = top + self.canvas.winfo_height()
        row_height = self._row_height(max(self.canvas.winfo_width(), 1))
        row_top = (index // 3) * row_height
        row_bottom = row_top + row_height
        if row_top < top:
            self.canvas.yview_moveto(row_top / max(1, self._content_height()))
        elif row_bottom > bottom:
            self.canvas.yview_moveto(max(0, row_bottom - self.canvas.winfo_height()) / max(1, self._content_height()))
        self.render()

    def set_photo(self, image_id: str, photo: ImageTk.PhotoImage) -> None:
        self.photos[image_id] = photo
        if image_id in self.drawn:
            self.canvas.itemconfigure(self.drawn[image_id][1], image=photo)

    def render(self, force=False) -> None:
        width = max(self.canvas.winfo_width(), 1)
        columns = 3
        rows = (len(self.items) + columns - 1) // columns
        row_height = self._row_height(width)
        self.canvas.configure(scrollregion=(0, 0, width, rows * row_height))
        first = max(0, int(self.canvas.canvasy(0) // row_height) - 1)
        last = min(rows, int((self.canvas.canvasy(0) + self.canvas.winfo_height()) // row_height) + 2)
        visible_items = self.items[first * 3:last * 3]
        visible = {item.image_id for item in visible_items}
        for image_id in tuple(self.drawn):
            if force or image_id not in visible:
                for object_id in self.drawn.pop(image_id):
                    self.canvas.delete(object_id)
                self.photos.pop(image_id, None)
        for index, item in enumerate(visible_items, start=first * 3):
            if item.image_id not in self.drawn:
                self._draw(index, item, width)
        self.on_visible(visible_items)

    def _draw(self, index, item, width):
        row, column = divmod(index, 3)
        card_width = max(1, width // 3)
        image_height = self._image_height(card_width)
        card_height = image_height + CARD_DETAILS_HEIGHT
        x = column * card_width + CARD_GUTTER
        y = row * self._row_height(width) + CARD_GUTTER
        rect = self.canvas.create_rectangle(x, y, x + card_width - CARD_GUTTER, y + card_height, fill=CARD, outline=BORDER, width=3)
        image = self.canvas.create_image(x + (card_width - CARD_GUTTER) // 2, y + image_height // 2, image=self.photos.get(item.image_id))
        name = self.canvas.create_text(x + 10, y + image_height + 10, text=item.file_path.name, fill=TEXT, anchor="nw", width=card_width - 28)
        status = self.canvas.create_text(x + 10, y + card_height - 12, text=self._status(item), fill=MUTED_TEXT, anchor="sw")
        objects = (rect, image, name, status)
        self.drawn[item.image_id] = objects
        for object_id in objects:
            self.canvas.tag_bind(object_id, "<Button-1>", lambda event, value=item.image_id: self.on_focus(value))
            self.canvas.tag_bind(object_id, "<Double-Button-1>", lambda event, value=item.image_id: self.on_open(value))
        self._style(item.image_id)

    def _style(self, image_id):
        item = self.items_by_id.get(image_id)
        if item is None:
            return
        rect, _, _, status = self.drawn[image_id]
        staged = self.staged_label_for(item)
        self.canvas.itemconfigure(rect, outline=FOCUS if image_id == self.focused_id else BORDER)
        self.canvas.itemconfigure(status, text=self._status(item), fill="#ffc857" if staged else "#b9e6a4" if item.reviewed else MUTED_TEXT)

    def _status(self, item):
        staged = self.staged_label_for(item)
        if staged and staged != item.current_label:
            return f"Staged: {item.current_label.title()} -> {staged.title()}"
        return "Staged: verified" if staged else "Verified" if item.reviewed else "Pending"

    def _content_height(self):
        return ((len(self.items) + 2) // 3) * self._row_height(max(self.canvas.winfo_width(), 1))

    def thumbnail_size(self) -> tuple[int, int]:
        card_width = max(1, self.canvas.winfo_width() // 3)
        return card_width - CARD_GUTTER * 2, self._image_height(card_width)

    @staticmethod
    def _image_height(card_width: int) -> int:
        return max(220, int((card_width - CARD_GUTTER * 2) * 0.75))

    def _row_height(self, width: int) -> int:
        return self._image_height(max(1, width // 3)) + CARD_DETAILS_HEIGHT + ROW_GUTTER

    def _scroll(self, *args):
        self.canvas.yview(*args)
        self.render()

    def _wheel(self, event):
        self._scroll_units(-3 if event.delta > 0 else 3)

    def _scroll_units(self, units):
        self.canvas.yview_scroll(units, "units")
        self.render()


class ReviewDetectionPreviewApp:
    def __init__(self, controller: ReviewDetectionPreviewController, session_path):
        self.controller, self.session_path = controller, session_path
        self.root = tk.Tk()
        self.root.title("Wildlife Vision Detection Review Preview")
        self.root.geometry("1400x900")
        self.root.minsize(960, 640)
        self.summary_var = tk.StringVar()
        self.preview_window = None
        self.generation = 0
        self.thumbnails = ThumbnailLoader()
        self._build_layout()
        register_bindings(self.root, on_move=self.move, on_verify=self.verify, on_relabel=self.relabel, on_cycle_label=self.cycle_label, on_preview=self.toggle_preview, on_save=self.save, on_close=self.handle_close)
        self.root.protocol("WM_DELETE_WINDOW", self.handle_close)
        self.load_active_label()
        self._poll_thumbnails()

    def _build_layout(self):
        self.root.configure(bg=BACKGROUND)
        self.root.columnconfigure(0, weight=1); self.root.columnconfigure(1, minsize=270); self.root.rowconfigure(0, weight=1)
        content = tk.Frame(self.root, bg=BACKGROUND, padx=12, pady=12); content.grid(row=0, column=0, sticky="nsew"); content.columnconfigure(0, weight=1); content.rowconfigure(2, weight=1)
        self.active_label_var = tk.StringVar()
        tk.Label(
            content,
            textvariable=self.active_label_var,
            bg=ACTIVE,
            fg=TEXT,
            anchor="w",
            font=("Helvetica", 16, "bold"),
            padx=12,
            pady=10,
            highlightthickness=1,
            highlightbackground=FOCUS,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))
        tabs = tk.Frame(content, bg=BACKGROUND); tabs.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        for column, label in enumerate(LABEL_ORDER):
            button = FlatButton(tabs, text="", command=lambda value=label: self.set_label(value))
            button.grid(row=0, column=column, sticky="ew", padx=(0, 4)); tabs.columnconfigure(column, weight=1); setattr(self, f"tab_{label}", button)
        shell = tk.Frame(content, bg=BACKGROUND, highlightthickness=1, highlightbackground=BORDER); shell.grid(row=2, column=0, sticky="nsew"); shell.columnconfigure(0, weight=1); shell.rowconfigure(0, weight=1)
        self.grid = VirtualGrid(shell, self.focus, self.open_from_card, self.request_visible_thumbnails)
        sidebar = tk.Frame(self.root, bg=PANEL, padx=16, pady=16, highlightthickness=1, highlightbackground=BORDER); sidebar.grid(row=0, column=1, sticky="nsew")
        tk.Label(sidebar, text="Detection Review", bg=PANEL, fg=TEXT, font=("Helvetica", 16, "bold"), anchor="w").pack(fill="x")
        tk.Label(sidebar, textvariable=self.summary_var, bg=PANEL, fg=MUTED_TEXT, anchor="w", justify="left").pack(fill="x", pady=(12, 18))
        actions = self._section(sidebar, "Actions")
        FlatButton(actions, text="Verify  Enter", command=self.verify).pack(fill="x", pady=(0, 6)); FlatButton(actions, text="Open image  Space", command=self.toggle_preview).pack(fill="x", pady=(0, 6)); FlatButton(actions, text="Save progress  Ctrl+S", command=self.save).pack(fill="x")
        shortcuts = self._section(sidebar, "Keyboard", pady=(18, 0))
        tk.Label(shortcuts, text="\n".join([*(f"{key}  Relabel as {label}" for key, label in LABEL_SHORTCUTS.items()), "Arrows  Move focus", "[ / ]  Switch label", "Esc  Exit"]), bg=CARD, fg=MUTED_TEXT, anchor="w", justify="left").pack(fill="x")

    def _section(self, parent, title: str, **pack_options):
        section = tk.Frame(parent, bg=CARD, padx=8, pady=8, highlightthickness=1, highlightbackground=BORDER)
        section.pack(fill="x", **pack_options)
        tk.Label(section, text=title, bg=CARD, fg=TEXT, anchor="w", font=("Helvetica", 11, "bold")).pack(fill="x", pady=(0, 8))
        return section

    def load_active_label(self):
        result = load_preview(LoadReviewDetectionPreviewInput(session_id=self.controller.state.session_id, include_reviewed=self.controller.state.include_reviewed, detection_label=self.controller.state.active_label))
        self.controller.replace_active_items(result.items, result.label_counts)
        self.generation += 1
        self.update_chrome(); self.grid.set_items(result.items, self._focused_id(), self.controller.staged_label_for)

    def update_chrome(self):
        self.active_label_var.set(f"Viewing: {self.controller.state.active_label.title()}")
        for label in LABEL_ORDER:
            getattr(self, f"tab_{label}").configure_state(
                text=f"{label.title()} ({self.controller.label_count(label)})",
                active=label == self.controller.state.active_label,
            )
        summary = self.controller.summary()
        self.summary_var.set(f"Active label: {self.controller.state.active_label.title()}\nImages: {self.controller.label_count(self.controller.state.active_label)}\nStaged: {summary.staged_decisions}\nVerify: {summary.same_label_reviews}\nRelabel: {summary.relabel_reviews}")

    def set_label(self, label):
        if self.controller.set_active_label(label): self.load_active_label()

    def cycle_label(self, direction):
        self.controller.cycle_label(direction); self.load_active_label()

    def move(self, row, column):
        _, current = self.controller.move_focus(row, column); self.grid.set_focus(current); self.grid.ensure_visible(self.controller.focused_index())

    def focus(self, image_id):
        _, current = self.controller.focus_item(image_id); self.grid.set_focus(current)

    def verify(self): self._stage(self.controller.verify_focused())
    def relabel(self, label): self._stage(self.controller.relabel_focused(label))
    def _stage(self, transition):
        old, current = transition
        if old is None: return
        self.grid.set_focus(current); self.grid._style(old); self.grid._style(current); self.grid.ensure_visible(self.controller.focused_index()); self.update_chrome()

    def request_visible_thumbnails(self, items):
        size = self.grid.thumbnail_size()
        for item in items:
            image = self.thumbnails.get(item.image_id, size)
            if image is not None: self.grid.set_photo(item.image_id, ImageTk.PhotoImage(image))
            else: self.thumbnails.request(item.image_id, item.file_path, size, self.generation)

    def _poll_thumbnails(self):
        for (image_id, size), generation, image in self.thumbnails.drain():
            if image is not None and image_id in self.grid.drawn:
                self.grid.set_photo(image_id, ImageTk.PhotoImage(image))
        if self.root.winfo_exists(): self.root.after(30, self._poll_thumbnails)

    def open_from_card(self, image_id): self.focus(image_id); self.open_preview()
    def toggle_preview(self): self._close_preview() if self.preview_window else self.open_preview()
    def open_preview(self):
        item = self.controller.focused_item()
        if item is None: return
        window = tk.Toplevel(self.root); self.preview_window = window; window.title(item.file_path.name); window.geometry("1100x800"); window.configure(bg="#111111"); window.protocol("WM_DELETE_WINDOW", self._close_preview)
        try:
            with Image.open(item.file_path) as image:
                preview = ImageOps.exif_transpose(image).convert("RGB"); preview.thumbnail((1000, 700), Image.Resampling.LANCZOS)
        except OSError as exc:
            self._close_preview(); messagebox.showerror("Cannot open image", str(exc), parent=self.root); return
        photo = ImageTk.PhotoImage(preview); label = tk.Label(window, image=photo, bg="#111111"); label.image = photo; label.pack(fill="both", expand=True, padx=12, pady=12); window.bind("<Escape>", lambda event: self._close_preview()); window.bind("<space>", lambda event: self._close_preview())
    def _close_preview(self):
        if self.preview_window and self.preview_window.winfo_exists(): self.preview_window.destroy()
        self.preview_window = None; self.root.focus_set()

    def save(self):
        if not self.controller.has_unsaved_changes(): return True
        if not messagebox.askokcancel("Save progress", self._format_summary(), parent=self.root): return False
        result = self.controller.commit(); self.load_active_label()
        if result.files_failed: messagebox.showerror("Some changes were not saved", self._format_result(result), parent=self.root); return False
        messagebox.showinfo("Progress saved", self._format_result(result), parent=self.root); return True
    def _format_summary(self):
        summary = self.controller.summary(); return f"Save {summary.staged_decisions} staged decisions?\n\nVerify current label: {summary.same_label_reviews}\nRelabel and move: {summary.relabel_reviews}"
    def _format_result(self, result: ApplyReviewDetectionResult): return f"Reviewed: {result.files_reviewed}\nRelabeled: {result.files_reassigned}\nMoved: {result.files_moved}\nFailed: {result.files_failed}"
    def handle_close(self):
        self._close_preview()
        if self.controller.has_unsaved_changes():
            choice = messagebox.askyesnocancel("Save changes?", "Save staged review decisions before exiting?", parent=self.root)
            if choice is None or (choice and not self.save()): return
        self.thumbnails.shutdown(); self.root.destroy()
    def run(self): self.root.mainloop()
    def _focused_id(self):
        item = self.controller.focused_item(); return None if item is None else item.image_id


def launch_review_detection_preview_app(session_id: str, include_reviewed: bool) -> None:
    result = load_preview(LoadReviewDetectionPreviewInput(session_id=session_id, include_reviewed=include_reviewed))
    if not any(result.label_counts.values()): logger.info("No reviewable images found in %s", display_path(result.session_path)); return
    logger.info("Launching detection review preview for %s%s", display_path(result.session_path), " (including reviewed)" if include_reviewed else "")
    ReviewDetectionPreviewApp(build_controller(result.session_id, include_reviewed, result.label_counts), result.session_path).run()
