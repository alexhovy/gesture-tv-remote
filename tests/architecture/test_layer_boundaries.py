import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"

FORBIDDEN_EXTERNALS = {
    "aiowebostv",
    "androidtvremote2",
    "cv2",
    "mediapipe",
    "rokuecp",
    "samsungtvws",
    "sounddevice",
    "sqlite3",
    "zeroconf",
}


class LayerBoundaryTests(unittest.TestCase):
    def test_services_package_has_been_removed(self) -> None:
        self.assertFalse((SRC_ROOT / "services").exists())

    def test_domain_is_pure(self) -> None:
        violations = _find_import_violations(
            SRC_ROOT / "domain",
            forbidden_prefixes=(
                "src.application",
                "src.infrastructure",
                "src.runtime",
                "src.web",
            ),
            forbidden_roots=FORBIDDEN_EXTERNALS,
        )

        self.assertEqual(violations, [])
        self.assertEqual(_find_dynamic_import_violations(SRC_ROOT / "domain"), [])

    def test_application_does_not_import_infrastructure_or_external_adapters(
        self,
    ) -> None:
        violations = _find_import_violations(
            SRC_ROOT / "application",
            forbidden_prefixes=(
                "src.infrastructure",
                "src.runtime",
                "src.web",
            ),
            forbidden_roots=FORBIDDEN_EXTERNALS,
        )

        self.assertEqual(violations, [])
        self.assertEqual(_find_dynamic_import_violations(SRC_ROOT / "application"), [])

    def test_infrastructure_does_not_import_runtime_or_web(self) -> None:
        violations = _find_import_violations(
            SRC_ROOT / "infrastructure",
            forbidden_prefixes=("src.runtime", "src.web"),
            forbidden_roots=set(),
        )

        self.assertEqual(violations, [])

    def test_web_does_not_import_infrastructure(self) -> None:
        violations = _find_import_violations(
            SRC_ROOT / "web",
            forbidden_prefixes=("src.infrastructure", "src.runtime"),
            forbidden_roots=FORBIDDEN_EXTERNALS,
        )

        self.assertEqual(violations, [])


def _find_import_violations(
    directory: Path,
    *,
    forbidden_prefixes: tuple[str, ...],
    forbidden_roots: set[str],
) -> list[str]:
    violations = []
    for path in sorted(directory.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for imported in _imports_from_node(node):
                root = imported.split(".", 1)[0]
                if root in forbidden_roots or imported.startswith(forbidden_prefixes):
                    relative_path = path.relative_to(PROJECT_ROOT)
                    violations.append(
                        f"{relative_path}:{getattr(node, 'lineno', 0)}: {imported}"
                    )
    return violations


def _imports_from_node(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module]
    return []


def _find_dynamic_import_violations(directory: Path) -> list[str]:
    violations = []
    for path in sorted(directory.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _is_dynamic_import_call(node):
                relative_path = path.relative_to(PROJECT_ROOT)
                violations.append(f"{relative_path}:{node.lineno}: dynamic import")
    return violations


def _is_dynamic_import_call(node: ast.Call) -> bool:
    function = node.func
    if isinstance(function, ast.Name):
        return function.id == "__import__"
    if not isinstance(function, ast.Attribute):
        return False
    if function.attr != "import_module":
        return False
    return isinstance(function.value, ast.Name) and function.value.id == "importlib"


if __name__ == "__main__":
    unittest.main()
