from pathlib import Path
import re

import pytest


def _read_main(repo_root: Path) -> str:
    main_path = repo_root / "app" / "main.py"
    if not main_path.exists():
        pytest.fail("expected file missing: app/main.py", pytrace=False)
    return main_path.read_text(encoding="utf-8")


def _extract_get_graph_storage_block(content: str) -> str:
    match = re.search(
        r"^def get_graph_storage\b[\s\S]*?(?=^def |^@|\Z)",
        content,
        flags=re.MULTILINE,
    )
    if not match:
        pytest.fail("get_graph_storage definition not found", pytrace=False)
    return match.group(0)


def test_get_graph_storage_uses_memgraph_storage():
    repo_root = Path(__file__).resolve().parents[2]
    content = _read_main(repo_root)
    block = _extract_get_graph_storage_block(content)

    if not re.search(r"\bMemgraphStorage\b", block):
        pytest.fail("get_graph_storage must construct MemgraphStorage", pytrace=False)
    if re.search(r"\bGraphStorage\b", block):
        pytest.fail("get_graph_storage must not construct GraphStorage", pytrace=False)
