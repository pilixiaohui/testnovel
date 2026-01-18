from __future__ import annotations

from pathlib import Path

from orchestrator.ui.server import _read_tail_text


def test_read_tail_text_returns_last_lines_and_eof_offset(tmp_path: Path) -> None:
    path = tmp_path / "orchestrator.log"
    path.write_text("a\nb\nc\nd\n", encoding="utf-8")

    text, end_offset = _read_tail_text(path=path, tail_lines=2)

    assert text == "c\nd\n"
    assert end_offset == path.stat().st_size


def test_read_tail_text_zero_lines_returns_empty_string(tmp_path: Path) -> None:
    path = tmp_path / "orchestrator.log"
    path.write_text("a\nb\n", encoding="utf-8")

    text, end_offset = _read_tail_text(path=path, tail_lines=0)

    assert text == ""
    assert end_offset == path.stat().st_size

