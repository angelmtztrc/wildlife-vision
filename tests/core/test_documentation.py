import importlib
import inspect
import pkgutil

import pytest

import wv.core


def _core_module_names() -> list[str]:
    return sorted(
        module.name
        for module in pkgutil.iter_modules(wv.core.__path__)
        if not module.name.startswith("_")
    )


@pytest.mark.parametrize("module_name", _core_module_names())
def test_public_core_functions_have_docstrings(module_name: str):
    module = importlib.import_module(f"wv.core.{module_name}")
    public_functions = [
        function
        for name, function in inspect.getmembers(module, inspect.isfunction)
        if function.__module__ == module.__name__ and not name.startswith("_")
    ]

    undocumented_functions = [
        function.__name__
        for function in public_functions
        if not inspect.getdoc(function)
    ]

    assert not undocumented_functions, (
        f"{module.__name__} public functions require docstrings: "
        f"{', '.join(undocumented_functions)}"
    )
