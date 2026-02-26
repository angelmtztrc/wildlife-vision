from pathlib import Path

allowed_image_exts = {".jpg", ".jpeg", ".png", ".heic"}


def is_allowed_image_file(file: Path) -> bool:
    return file.suffix.lower() in allowed_image_exts
