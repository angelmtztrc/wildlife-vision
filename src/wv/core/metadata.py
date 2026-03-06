import re
from typing import Literal
from pathlib import Path

from wv.core.exif import read_exif, write_exif_image_description

AvailableMetadataTags = Literal["Detection", "Coordinates", "Species"]
AvailableDetections = Literal["empty", "animal", "irrelevant"]


def _is_valid_metadata_format(metadata: str) -> bool:
    """
    Check if the given metadata string is in a valid format. The expected format is: Tag=value;Tag=value;... where Tag is a valid metadata tag and value is any string that does not contain a semicolon.

    Args:
        metadata (str): The metadata string to validate.

    Returns:
        bool: True if the metadata string is in a valid format, False otherwise.
    """
    if not metadata or not isinstance(metadata, str):
        return False

    pattern = r"^([A-Za-z_][A-Za-z0-9_]*=[^;]+;)+$"

    return bool(re.match(pattern, metadata))


def _parse_metadata(metadata: str) -> dict[str, str]:
    """
    Parse a metadata string in the format Tag=value;Tag=value;... into a dictionary.

    Args:
        metadata (str): The metadata string to parse.

    Returns:
        dict[str, str]: A dictionary containing the parsed metadata tags and their corresponding values.
    """
    if not _is_valid_metadata_format(metadata):
        return {}

    metadata_dict = {}
    pairs = metadata.split(";")
    for pair in pairs:
        if pair:
            tag, value = pair.split("=", 1)
            metadata_dict[tag] = value

    return metadata_dict


def read_metadata(image_path: Path):
    """
    Read metadata from an image file. The metadata is expected to be stored in the ImageDescription EXIF tag in the format Tag=value;Tag=value;...

    Args:
        image_path (Path): The path to the image file from which to read metadata.

    Returns:
        dict[str, str]: A dictionary containing the parsed metadata tags and their corresponding values.
    """

    metadata = read_exif(image_path, "ImageDescription")

    return _parse_metadata(metadata)


def set_metadata(image_path: Path, tag_name: AvailableMetadataTags, tag_value: str):
    """
    Set a specific metadata tag and value for an image file. The metadata will be stored in the ImageDescription EXIF tag in the format Tag=value;Tag=value;...

    Args:
        image_path (Path): The path to the image file for which to set metadata.
        tag_name (AvailableMetadataTags): The name of the metadata tag to set.
        tag_value (str): The value to set for the specified metadata tag.
    """

    metadata = read_metadata(image_path)

    metadata[tag_name] = tag_value

    mutated_metadata_str = ";".join(f"{key}={value}" for key, value in metadata.items())

    write_exif_image_description(image_path, mutated_metadata_str)


def remove_metadata(image_path: Path, tag_name: AvailableMetadataTags):
    """
    Remove a specific metadata tag from an image file. The metadata is stored in the ImageDescription EXIF tag in the format Tag=value;Tag=value;...

    Args:
        image_path (Path): The path to the image file from which to remove metadata.
        tag_name (AvailableMetadataTags): The name of the metadata tag to remove.
    """
    metadata = read_metadata(image_path)

    if tag_name in metadata:
        del metadata[tag_name]

    mutated_metadata_str = ";".join(f"{key}={value}" for key, value in metadata.items())

    write_exif_image_description(image_path, mutated_metadata_str)
