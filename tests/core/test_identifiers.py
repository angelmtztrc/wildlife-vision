import pytest

from wv.core.identifiers import normalize_catalog_identifier


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Rancho El Cascabel", "RANCHO_EL_CASCABEL"),
        ("Árbol caído", "ARBOL_CAIDO"),
        ("Border-fence trail", "BORDER_FENCE_TRAIL"),
        ("  Riverside #2 ", "RIVERSIDE_2"),
    ],
)
def test_normalize_catalog_identifier(value: str, expected: str):
    assert normalize_catalog_identifier(value) == expected


def test_normalize_catalog_identifier_rejects_empty_result():
    with pytest.raises(ValueError, match="letter or digit"):
        normalize_catalog_identifier("---")
