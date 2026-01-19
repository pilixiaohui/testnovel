from __future__ import annotations

import argparse
import re
from pathlib import Path


_TASK_HEADER_RE = re.compile(r"^###\s+([^:]+):\s*(.*)$")
# NOTE: allow optional leading "-" to reduce brittleness for LLM-written markdown.
_STATUS_RE = re.compile(r"^\s*(?:-\s*)?status:\s*([A-Z]+)\s*$")
_ACCEPTANCE_RE = re.compile(r"^\s*(?:-\s*)?acceptance:\s*(.*)$")
_EVIDENCE_RE = re.compile(r"^\s*(?:-\s*)?evidence:\s*(.*)$")
_PHASE_HEADER_RE = re.compile(r"^####\s+(测试阶段|实现阶段|审阅阶段)\s*$")


def _split_task_blocks(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    """
    Split dev_plan.md into (preamble, task_blocks).

    A task block starts at a line beginning with '### ' and continues until the next task header or EOF.
    """
    preamble: list[str] = []
    blocks: list[list[str]] = []
    current: list[str] | None = None

    for line in lines:
        if line.startswith("### "):
            if current is None:
                current = [line]
            else:
                blocks.append(current)
                current = [line]
            continue

        if current is None:
            preamble.append(line)
        else:
            current.append(line)

    if current is not None:
        blocks.append(current)

    return preamble, blocks


def _convert_task_block(block: list[str]) -> list[str]:
    """
    Convert a legacy task block (single status/acceptance/evidence) into the phased format.
    """
    if not block or not block[0].startswith("### "):
        raise RuntimeError("invalid task block (missing header)")
    if any(_PHASE_HEADER_RE.match(line) for line in block):
        return block

    header = block[0]
    body = block[1:]

    status_values: list[str] = []
    acceptance_idx: int | None = None
    evidence_idx: int | None = None

    for idx, line in enumerate(body):
        m = _STATUS_RE.match(line)
        if m:
            status_values.append(m.group(1).strip())
            continue
        if acceptance_idx is None and _ACCEPTANCE_RE.match(line):
            acceptance_idx = idx
            continue
        if evidence_idx is None and _EVIDENCE_RE.match(line):
            evidence_idx = idx
            continue

    if not status_values:
        raise RuntimeError(f"task missing status: {header!r}")
    if acceptance_idx is None:
        raise RuntimeError(f"task missing acceptance: {header!r}")
    if evidence_idx is None:
        raise RuntimeError(f"task missing evidence: {header!r}")

    overall_status = status_values[-1]
    if overall_status == "VERIFIED":
        test_status = "DONE"
        impl_status = "DONE"
        review_status = "VERIFIED"
    else:
        test_status = overall_status
        impl_status = overall_status
        review_status = overall_status

    meta_lines: list[str] = []
    for line in body[:acceptance_idx]:
        # Drop legacy status/evidence lines; keep everything else (e.g. task_type/test_required).
        if _STATUS_RE.match(line) or _EVIDENCE_RE.match(line):
            continue
        meta_lines.append(line)

    acceptance_block = body[acceptance_idx:evidence_idx]
    evidence_block = [line for line in body[evidence_idx:] if not _STATUS_RE.match(line)]

    out: list[str] = []
    out.append(header)
    out.extend(meta_lines)
    out.extend(acceptance_block)
    if out and out[-1].strip():
        out.append("")

    out.extend(
        [
            "#### 测试阶段",
            f"- status: {test_status}",
            "- evidence:",
            "",
            "#### 实现阶段",
            f"- status: {impl_status}",
            "- evidence:",
            "",
            "#### 审阅阶段",
            f"- status: {review_status}",
        ]
    )
    out.extend(evidence_block)
    return out


def migrate_dev_plan_phases(*, input_path: Path, output_path: Path) -> None:
    raw = input_path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    preamble, blocks = _split_task_blocks(lines)
    converted: list[str] = []
    converted.extend(preamble)
    for block in blocks:
        converted.extend(_convert_task_block(block))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(converted).rstrip() + "\n", encoding="utf-8")


def _main() -> None:
    parser = argparse.ArgumentParser(description="Migrate dev_plan.md to phased task format (backward compatible).")
    parser.add_argument("--input", required=True, help="Input dev_plan.md path (utf-8)")
    parser.add_argument("--output", required=True, help="Output path for migrated dev_plan.md (utf-8)")
    args = parser.parse_args()
    migrate_dev_plan_phases(input_path=Path(args.input), output_path=Path(args.output))


if __name__ == "__main__":
    _main()

