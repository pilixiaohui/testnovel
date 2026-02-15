from pathlib import Path
import re

import pytest

ENTRYPOINTS = [
    "app/main.py",
    "app/storage/ports.py",
]
FORBIDDEN_TOKENS = [
    "kuzu_db_path",
    "app.storage.graph",
    "from app.storage import graph",
    "import app.storage.graph",
]
PYPROJECT_REL_PATH = "pyproject.toml"


def _read_text(target: Path, rel_label: str) -> str:
    if not target.exists():
        pytest.fail(f"expected file missing: {rel_label}", pytrace=False)
    return target.read_text(encoding="utf-8")


def _iter_source_files(root: Path) -> list[Path]:
    if not root.exists():
        pytest.fail(f"expected directory missing: {root}", pytrace=False)
    return sorted(
        path
        for path in root.rglob("*.py")
        if path.is_file() and "__pycache__" not in path.parts
    )


def test_entrypoints_do_not_reference_kuzu():
    repo_root = Path(__file__).resolve().parents[2]
    violations: list[str] = []

    for rel_path in ENTRYPOINTS:
        content = _read_text(repo_root / rel_path, rel_path)
        lowered = content.lower()
        for token in FORBIDDEN_TOKENS:
            if token in lowered:
                violations.append(f"{rel_path} contains '{token}'")

    if violations:
        pytest.fail(
            "Kuzu references still present in entrypoints:\n" + "\n".join(violations),
            pytrace=False,
        )


def test_main_entrypoint_no_kuzu_env_or_graphstorage():
    repo_root = Path(__file__).resolve().parents[2]
    content = _read_text(repo_root / "app" / "main.py", "app/main.py")
    violations: list[str] = []

    if "KUZU_DB_PATH" in content:
        violations.append("app/main.py contains KUZU_DB_PATH")
    if re.search(r"\bGraphStorage\b", content):
        violations.append("app/main.py contains GraphStorage")

    if violations:
        pytest.fail(
            "main.py still contains Kuzu graph wiring:\n" + "\n".join(violations),
            pytrace=False,
        )


def test_app_and_scripts_do_not_reference_kuzu():
    repo_root = Path(__file__).resolve().parents[2]
    project_root = repo_root.parent
    targets = [repo_root / "app", project_root / "scripts"]
    violations: list[str] = []

    for target in targets:
        for path in _iter_source_files(target):
            content = path.read_text(encoding="utf-8")
            if "kuzu" in content.lower():
                violations.append(str(path.relative_to(project_root)))

    if violations:
        pytest.fail(
            "Kuzu references still present in app/scripts:\n" + "\n".join(violations),
            pytrace=False,
        )


def test_pyproject_does_not_depend_on_kuzu():
    repo_root = Path(__file__).resolve().parents[2]
    content = _read_text(repo_root / PYPROJECT_REL_PATH, PYPROJECT_REL_PATH)
    if "kuzu" in content.lower():
        pytest.fail("pyproject.toml still references kuzu dependency", pytrace=False)
