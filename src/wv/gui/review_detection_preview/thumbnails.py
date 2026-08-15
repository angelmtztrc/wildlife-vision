from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from queue import Empty, Queue

from PIL import Image, ImageOps


def _decode(path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as image:
        thumbnail = ImageOps.exif_transpose(image).convert("RGB")
        thumbnail.thumbnail(size, Image.Resampling.LANCZOS)
        return thumbnail.copy()


class ThumbnailLoader:
    """Decode bounded thumbnail images outside the Tk event loop."""

    def __init__(self, cache_size: int = 48):
        self.cache_size = cache_size
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="wv-thumbnail")
        self._pending: set[tuple[str, tuple[int, int]]] = set()
        self._results: Queue[tuple[tuple[str, tuple[int, int]], int, Image.Image | None]] = Queue()
        self._cache: OrderedDict[tuple[str, tuple[int, int]], Image.Image] = OrderedDict()

    def get(self, image_id: str, size: tuple[int, int]) -> Image.Image | None:
        key = (image_id, size)
        image = self._cache.get(key)
        if image is not None:
            self._cache.move_to_end(key)
        return image

    def request(self, image_id: str, path: Path, size: tuple[int, int], generation: int) -> None:
        key = (image_id, size)
        if key in self._pending or self.get(image_id, size) is not None:
            return
        self._pending.add(key)
        future = self._executor.submit(_decode, path, size)
        future.add_done_callback(
            lambda completed, token=generation: self._complete(key, token, completed)
        )

    def drain(self) -> list[tuple[tuple[str, tuple[int, int]], int, Image.Image | None]]:
        results: list[tuple[tuple[str, tuple[int, int]], int, Image.Image | None]] = []
        while True:
            try:
                result = self._results.get_nowait()
            except Empty:
                break
            self._pending.discard(result[0])
            if result[2] is not None:
                self._cache[result[0]] = result[2]
                self._cache.move_to_end(result[0])
                while len(self._cache) > self.cache_size:
                    self._cache.popitem(last=False)
            results.append(result)
        return results

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _complete(
        self,
        key: tuple[str, tuple[int, int]],
        generation: int,
        future: Future[Image.Image],
    ) -> None:
        try:
            image = future.result()
        except OSError:
            image = None
        self._results.put((key, generation, image))
