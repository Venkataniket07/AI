import ast
from pathlib import Path


def get_imported_modules(source: str) -> list[tuple[str, int]]:
    tree = ast.parse(source)
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imports.append((node.module, node.lineno))
    return imports


def find_import_violations(source: str, forbidden_roots: set[str]) -> list[tuple[str, int]]:
    violations: list[tuple[str, int]] = []
    for mod, lineno in get_imported_modules(source):
        root = mod.split(".")[0]
        if root in forbidden_roots:
            violations.append((mod, lineno))
    return violations


def check_directory_imports(directory: Path, forbidden_roots: set[str]) -> list[str]:
    violations: list[str] = []
    for py_file in sorted(directory.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        file_violations = find_import_violations(source, forbidden_roots)
        for mod, lineno in file_violations:
            violations.append(f"{py_file.as_posix()}:{lineno} imports forbidden '{mod}'")
    return violations


def test_violating_source_detected():
    source = "import games.assist\nfrom ai.config import config\nimport os\n"
    violations = find_import_violations(source, {"games", "ai"})
    assert len(violations) == 2
    assert violations[0][0] == "games.assist"
    assert violations[1][0] == "ai.config"


def test_core_does_not_import_games_or_ai():
    repo_root = Path(__file__).resolve().parent.parent
    violations = check_directory_imports(repo_root / "core", {"games", "ai"})
    assert not violations, "Forbidden imports in core/:\n" + "\n".join(violations)


def test_ai_does_not_import_games():
    repo_root = Path(__file__).resolve().parent.parent
    violations = check_directory_imports(repo_root / "ai", {"games"})
    assert not violations, "Forbidden imports in ai/:\n" + "\n".join(violations)
