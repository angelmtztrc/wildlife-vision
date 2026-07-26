from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageTk

from wv.core.display import display_path
from wv.core.logger import get_logger
from wv.gui.review.bindings import register_bindings
from wv.gui.review.controller import ReviewController, build_controller
from wv.use_cases.review.apply import ApplyReviewResult
from wv.use_cases.review.load import LoadReviewSessionInput, run as load_review_session

logger = get_logger(__name__)


class ReviewApp:
    def __init__(self, controller: ReviewController):
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("Wildlife Vision Review")
        self.root.geometry("1280x900")
        self.root.minsize(800, 600)

        self.header_var = tk.StringVar()
        self.detail_var = tk.StringVar()
        self.zoom_var = tk.StringVar()

        self.current_image = None
        self.current_photo = None

        self._build_layout()
        register_bindings(
            root=self.root,
            controller=self.controller,
            refresh=self.refresh,
            on_save=self.save_and_exit,
            on_close=self.handle_close,
        )
        self.root.protocol("WM_DELETE_WINDOW", self.handle_close)
        self.image_frame.bind("<Configure>", lambda event: self.refresh())
        self.refresh()

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = tk.Frame(self.root, padx=12, pady=12)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        tk.Label(header, textvariable=self.header_var, anchor="w", font=("Helvetica", 16, "bold")).grid(row=0, column=0, sticky="ew")
        tk.Label(header, textvariable=self.detail_var, anchor="w", justify="left").grid(row=1, column=0, sticky="ew", pady=(6, 0))

        self.image_frame = tk.Frame(self.root, bg="#111111")
        self.image_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.image_frame.columnconfigure(0, weight=1)
        self.image_frame.rowconfigure(0, weight=1)

        self.image_label = tk.Label(self.image_frame, bg="#111111")
        self.image_label.grid(row=0, column=0, sticky="nsew")

        footer = tk.Frame(self.root, padx=12, pady=12)
        footer.grid(row=2, column=0, sticky="ew")

        for label, key in (
            ("1 Animal", "animal"),
            ("2 Human", "human"),
            ("3 Vehicle", "vehicle"),
            ("4 Empty", "empty"),
            ("5 Other", "other"),
        ):
            tk.Button(footer, text=label, command=lambda value=key: self._assign_and_refresh(value)).pack(side="left", padx=(0, 6))

        tk.Button(footer, text="Prev", command=self._previous_and_refresh).pack(side="left", padx=(12, 6))
        tk.Button(footer, text="Skip", command=self._skip_and_refresh).pack(side="left", padx=(0, 6))
        tk.Button(footer, text="Next", command=self._next_and_refresh).pack(side="left", padx=(0, 6))
        tk.Button(footer, text="Zoom +", command=self._zoom_in_and_refresh).pack(side="left", padx=(12, 6))
        tk.Button(footer, text="Zoom -", command=self._zoom_out_and_refresh).pack(side="left", padx=(0, 6))
        tk.Button(footer, text="Reset Zoom", command=self._reset_zoom_and_refresh).pack(side="left", padx=(0, 6))
        tk.Label(footer, textvariable=self.zoom_var).pack(side="right", padx=(6, 0))
        tk.Button(footer, text="Save & Exit", command=self.save_and_exit).pack(side="right")

    def _assign_and_refresh(self, label: str) -> None:
        self.controller.assign_label(label)
        self.refresh()

    def _previous_and_refresh(self) -> None:
        self.controller.previous_image()
        self.refresh()

    def _skip_and_refresh(self) -> None:
        self.controller.skip_current()
        self.refresh()

    def _next_and_refresh(self) -> None:
        self.controller.next_image()
        self.refresh()

    def _zoom_in_and_refresh(self) -> None:
        self.controller.zoom_in()
        self.refresh()

    def _zoom_out_and_refresh(self) -> None:
        self.controller.zoom_out()
        self.refresh()

    def _reset_zoom_and_refresh(self) -> None:
        self.controller.reset_zoom()
        self.refresh()

    def _render_image(self, file_path: Path) -> None:
        frame_width = max(self.image_frame.winfo_width(), 1)
        frame_height = max(self.image_frame.winfo_height(), 1)

        with Image.open(file_path) as image:
            self.current_image = image.copy()

        base_image = self.current_image
        width, height = base_image.size
        fit_scale = min(frame_width / width, frame_height / height, 1.0)
        scale = max(fit_scale * self.controller.state.zoom_scale, 0.05)
        resized = base_image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.LANCZOS,
        )
        self.current_photo = ImageTk.PhotoImage(resized)
        self.image_label.configure(image=self.current_photo)

    def refresh(self) -> None:
        item = self.controller.current_item()
        if item is None:
            self.header_var.set("No images to review")
            self.detail_var.set("This detection bucket has no supported images matching the current filter.")
            self.zoom_var.set("Zoom 100%")
            self.image_label.configure(image="")
            return

        current, total = self.controller.current_position()
        staged_label = self.controller.staged_label_for_current()
        self.header_var.set(f"{current}/{total}  {item.file_path.name}")
        self.detail_var.set(
            f"Original label: {item.original_label}    Staged label: {staged_label or '-'}    Reviewed: {'yes' if item.reviewed else 'no'}"
        )
        self.zoom_var.set(f"Zoom {int(self.controller.state.zoom_scale * 100)}%")
        self._render_image(item.file_path)

    def _format_summary(self) -> str:
        summary = self.controller.summary()
        return (
            f"Staged decisions: {summary.staged_decisions}\n"
            f"Same-label reviews: {summary.same_label_reviews}\n"
            f"Relabel reviews: {summary.relabel_reviews}\n"
            f"Moves: {summary.move_count}\n"
            f"Metadata-only updates: {summary.metadata_only_count}"
        )

    def _format_commit_result(self, result: ApplyReviewResult) -> str:
        failures = [
            f"- {item_result.original_path.name}: {item_result.failure}"
            for item_result in result.item_results
            if not item_result.success and item_result.failure
        ]
        lines = [
            f"Reviewed: {result.files_reviewed}",
            f"Relabeled: {result.files_reassigned}",
            f"Moved: {result.files_moved}",
            f"Replaced: {result.files_replaced}",
            f"Failed: {result.files_failed}",
        ]
        if failures:
            lines.extend(["", "Failures:", *failures])
        return "\n".join(lines)

    def save_and_exit(self) -> None:
        if not self.controller.has_unsaved_changes():
            self.root.destroy()
            return

        if not messagebox.askokcancel("Save & Exit", self._format_summary()):
            return

        result = self.controller.commit()
        if result.files_failed > 0:
            messagebox.showerror(
                "Save failed",
                self._format_commit_result(result),
            )
            self.refresh()
            return

        messagebox.showinfo("Saved", self._format_commit_result(result))
        self.root.destroy()

    def handle_close(self) -> None:
        if self.controller.has_unsaved_changes() and not messagebox.askyesno(
            "Discard changes",
            "You have unsaved staged review decisions. Discard them and exit?",
        ):
            return

        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def launch_review_app(session_path: Path, detection_label: str, pending_only: bool) -> None:
    result = load_review_session(
        LoadReviewSessionInput(
            session_path=session_path,
            detection_label=detection_label,
            pending_only=pending_only,
        )
    )

    if not result.items:
        logger.info(
            "No reviewable images found in %s",
            display_path(result.source_directory),
        )
        return

    logger.info(
        "Launching review GUI for %s with %s images%s",
        display_path(result.source_directory),
        len(result.items),
        " (pending only)" if pending_only else "",
    )
    app = ReviewApp(
        controller=build_controller(
            session_path=session_path,
            source_label=detection_label,
            items=result.items,
        )
    )
    app.run()
