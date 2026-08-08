from collections.abc import Callable

from wv.gui.favorites.controller import FavoriteController


def register_bindings(
    root,
    controller: FavoriteController,
    refresh: Callable[[], None],
    on_save: Callable[[], None],
    on_close: Callable[[], None],
) -> None:
    root.bind("f", lambda event: _run(controller.favorite_current, refresh))
    root.bind("u", lambda event: _run(controller.unfavorite_current, refresh))
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


def _run(action: Callable[[], None], refresh: Callable[[], None]) -> None:
    action()
    refresh()
