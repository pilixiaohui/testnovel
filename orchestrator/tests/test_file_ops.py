from pathlib import Path
from tempfile import TemporaryDirectory

from orchestrator.file_ops import _atomic_write_text


def test_atomic_write_text_writes_content() -> None:
    with TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "sample.txt"
        _atomic_write_text(path, "hello\n")
        assert path.read_text(encoding="utf-8") == "hello\n"
