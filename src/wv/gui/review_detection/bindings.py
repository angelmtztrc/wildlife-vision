from collections.abc import Callable

from wv.gui.review_detection.controller import ReviewController


def register_bindings(root, controller: ReviewController, refresh: Callable[[], None], on_save: Callable[[], None], on_close: Callable[[], None]) -> None:
    root.bind("1", lambda event: _assign(controller, "animal", refresh))
    root.bind("2", lambda event: _assign(controller, "human", refresh))
    root.bind("3", lambda event: _assign(controller, "vehicle", refresh))
    root.bind("4", lambda event: _assign(controller, "empty", refresh))
    root.bind("5", lambda event: _assign(controller, "other", refresh))
    root.bind("<space>", lambda event: _run(controller.skip_current, refresh))
    root.bind("<Right>", lambda event: _run(controller.next_image, refresh))
    root.bind("n", lambda event: _run(controller.next_image, refresh))
    root.bind("<Left>", lambda event: _run(controller.previous_image, refresh))
    root.bind("p", lambda event: _run(controller.previous_image, refresh))
    root.bind("+", lambda event: _run(controller.zoom_in, refresh))
    root.bind("=", lambda event: _run(controller.zoom_in, refresh))
    root.bind("-", lambda event: _run(controller.zoom_out, refresh))
    root.bind("0", lambda event: _run(controller.reset_zoom, refresh))
    root.bind("<Control-s>", lambda event: on_save())
    root.bind("<Escape>", lambda event: on_close())


def _assign(controller: ReviewController, label: str, refresh: Callable[[], None]) -> None:
    controller.assign_label(label)
    refresh()


def _run(action: Callable[[], None], refresh: Callable[[], None]) -> None:
    action()
    refresh()
