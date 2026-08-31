from collections.abc import Callable

from wv.gui.review_detection_preview.controller import LABEL_SHORTCUTS


def register_bindings(
    root,
    *,
    on_move: Callable[[int, int], None],
    on_verify: Callable[[], None],
    on_relabel: Callable[[str], None],
    on_cycle_label: Callable[[int], None],
    on_preview: Callable[[], None],
    on_save: Callable[[], None],
    on_close: Callable[[], None],
) -> None:
    for key, label in LABEL_SHORTCUTS.items():
        root.bind(str(key), lambda event, value=label: on_relabel(value))
    root.bind("<Return>", lambda event: on_verify())
    root.bind("<space>", lambda event: on_preview())
    root.bind("<Left>", lambda event: on_move(0, -1))
    root.bind("<Right>", lambda event: on_move(0, 1))
    root.bind("<Up>", lambda event: on_move(-1, 0))
    root.bind("<Down>", lambda event: on_move(1, 0))
    root.bind("[", lambda event: on_cycle_label(-1))
    root.bind("]", lambda event: on_cycle_label(1))
    root.bind("<Control-s>", lambda event: on_save())
    root.bind("<Escape>", lambda event: on_close())
