import ast
from pathlib import Path


USE_CASES_ROOT = Path(__file__).parents[2] / "src" / "wv" / "use_cases"
WORKFLOW_MODULES = {
    USE_CASES_ROOT / "pipeline" / "preprocess.py",
}


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _python_files() -> list[Path]:
    return sorted(USE_CASES_ROOT.rglob("*.py"))


def _top_level_functions(module: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def test_operation_modules_expose_single_run_entrypoint():
    offenders: list[str] = []

    for path in _python_files():
        if path.name in {"__init__.py", "_shared.py"}:
            continue

        functions = _top_level_functions(_parse(path))
        public_functions = [function.name for function in functions if not function.name.startswith("_")]

        if "run" not in public_functions:
            offenders.append(f"{path.relative_to(USE_CASES_ROOT)}: missing run()")
        extra_entries = [name for name in public_functions if name.startswith("run_")]
        if extra_entries:
            offenders.append(
                f"{path.relative_to(USE_CASES_ROOT)}: unexpected {', '.join(extra_entries)}"
            )

    assert offenders == []


def test_use_case_package_initializers_do_not_reexport_operation_apis():
    offenders: list[str] = []

    for path in _python_files():
        if path.name != "__init__.py":
            continue

        imports = [
            node
            for node in _parse(path).body
            if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        if imports:
            offenders.append(str(path.relative_to(USE_CASES_ROOT)))

    assert offenders == []


def test_use_case_modules_do_not_import_other_use_case_modules_except_workflows():
    offenders: list[str] = []

    for path in _python_files():
        if path in WORKFLOW_MODULES:
            continue

        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.ImportFrom) and node.module == "wv.use_cases":
                offenders.append(f"{path.relative_to(USE_CASES_ROOT)}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("wv.use_cases."):
                offenders.append(f"{path.relative_to(USE_CASES_ROOT)}:{node.lineno}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "wv.use_cases" or alias.name.startswith("wv.use_cases."):
                        offenders.append(f"{path.relative_to(USE_CASES_ROOT)}:{node.lineno}")

    assert offenders == []
