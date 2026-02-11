from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from .config import (
    DEV_PLAN_FILE,
    DEV_PLAN_STAGED_FILE,
    IMPLEMENTER_TASK_FILE,
    ITERATION_ARCHIVE_DIR,
    MEMORY_BACKUP_DIR,
    REPORT_IMPLEMENTER_FILE,
    REPORT_ITERATION_SUMMARY_FILE,
    REPORT_MAIN_DECISION_FILE,
    REPORTS_BACKUP_DIR,
    SYNTHESIZER_REPORT_FILE,
    VALIDATION_RESULTS_FILE,
    VALIDATOR_REPORTS_DIR,
    VALIDATOR_WORKSPACE_DIR,
    PARALLEL_VALIDATORS,
    WORKSPACE_BACKUP_DIR,
)
from .file_ops import _append_log_line, _atomic_write_text, _read_text, _rel_path, _require_file, _sha256_text
from .validation import _validate_dev_plan_text, _validate_session_id


def _clear_dev_plan_stage_file() -> None:
    if DEV_PLAN_STAGED_FILE.exists():  # 关键分支：仅在存在时删除
        DEV_PLAN_STAGED_FILE.unlink()


def _backup_md_file(*, src: Path, dest_dir: Path, name: str, stamp: str, session_id: str) -> Path:
    _validate_session_id(session_id)
    if not src.exists():  # 关键分支：源文件不存在直接失败
        raise FileNotFoundError(f"Missing backup source file: {src}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{name}__{stamp}__{session_id}.md"  # 关键变量：备份文件路径
    content = src.read_text(encoding="utf-8")  # 关键变量：源文件内容
    dest.write_text(content, encoding="utf-8")  # 关键变量：写入备份内容
    return dest


def _backup_subagent_artifacts(*, agent: str, session_id: str, report_file: Path, task_file: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")  # 关键变量：备份时间戳
    report_name = f"report_{agent.lower()}"  # 关键变量：报告备份名前缀
    task_name = f"current_task_{agent.lower()}"  # 关键变量：工单备份名前缀
    backed_report = _backup_md_file(
        src=report_file,
        dest_dir=REPORTS_BACKUP_DIR,
        name=report_name,
        stamp=stamp,
        session_id=session_id,
    )
    backed_task = _backup_md_file(
        src=task_file,
        dest_dir=WORKSPACE_BACKUP_DIR,
        name=task_name,
        stamp=stamp,
        session_id=session_id,
    )
    _append_log_line(
        "orchestrator: backup_saved "
        f"report={_rel_path(backed_report)} task={_rel_path(backed_task)}\n"
    )


def _commit_staged_dev_plan_if_present(
    *,
    iteration: int,
    main_session_id: str,
    dev_plan_before_hash: str,
) -> None:
    """
    dev_plan 写入接口（容忍直接编辑）：
    - 优先使用 staged 文件（JSON dev_plan_next）覆盖 dev_plan
    - 若无 staged 但 MAIN 直接编辑了 dev_plan，校验后接受
    - 若两者都没变，什么都不做
    """
    _validate_session_id(main_session_id)  # 关键变量：会话 id 必须合法
    _require_file(DEV_PLAN_FILE)  # 关键分支：dev_plan 必须存在
    after_hash = _sha256_text(_read_text(DEV_PLAN_FILE))  # 关键变量：运行后哈希
    dev_plan_directly_edited = (after_hash != dev_plan_before_hash)
    has_staged = DEV_PLAN_STAGED_FILE.exists()

    if has_staged:
        # JSON dev_plan_next 优先：读取 staged，校验，备份旧版，覆盖写入
        staged_raw = _read_text(DEV_PLAN_STAGED_FILE)  # 关键变量：草案原始内容
        staged = staged_raw.rstrip()  # 关键变量：去尾空白后的草案
        if not staged.strip():  # 关键分支：空草案直接失败
            raise RuntimeError(f"Empty staged dev_plan file: {DEV_PLAN_STAGED_FILE}")

        _validate_dev_plan_text(text=staged, source=DEV_PLAN_STAGED_FILE)  # 关键变量：草案校验
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")  # 关键变量：备份时间戳
        backed = _backup_md_file(
            src=DEV_PLAN_FILE,
            dest_dir=MEMORY_BACKUP_DIR,
            name=f"dev_plan_pre_iter{iteration}",
            stamp=stamp,
            session_id=main_session_id,
        )
        if dev_plan_directly_edited:
            _append_log_line(
                "orchestrator: dev_plan was directly edited by MAIN, "
                "but JSON dev_plan_next takes precedence (overwriting direct edit)\n"
            )
        _atomic_write_text(DEV_PLAN_FILE, staged + "\n")  # 关键变量：原子覆盖 dev_plan
        DEV_PLAN_STAGED_FILE.unlink()  # 关键变量：清理草案
        _append_log_line(
            "orchestrator: dev_plan_committed "
            f"backup={_rel_path(backed)}\n"
        )

    elif dev_plan_directly_edited:
        # 没有 staged，但 MAIN 直接编辑了 dev_plan → 校验后接受
        direct_content = _read_text(DEV_PLAN_FILE).rstrip()
        if not direct_content.strip():
            raise RuntimeError("MAIN directly edited dev_plan.md but left it empty")
        _validate_dev_plan_text(text=direct_content, source=DEV_PLAN_FILE)
        _append_log_line(
            "orchestrator: dev_plan directly edited by MAIN (no JSON dev_plan_next), "
            "accepting direct edit after validation\n"
        )
    # else: 两者都没变，什么都不做


def _summary_matches_iteration(*, summary_file: Path, iteration: int) -> bool:
    """校验 summary 文件是否属于目标迭代。"""
    try:
        payload = json.loads(summary_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("iteration") == iteration


_REPORT_ITERATION_RE = re.compile(r"^\s*iteration:\s*(\d+)\s*$", re.IGNORECASE | re.MULTILINE)
_TASK_ITERATION_RE = re.compile(r"^#\s*Current\s+Task\s*\(Iteration\s*(\d+)\)\s*$", re.IGNORECASE | re.MULTILINE)


def _assert_markdown_iteration(*, src: Path, iteration: int) -> None:
    text = src.read_text(encoding="utf-8")
    match = _REPORT_ITERATION_RE.search(text)
    if not match:
        raise RuntimeError(f"Missing iteration marker in {_rel_path(src)}")
    parsed = int(match.group(1))
    if parsed != iteration:
        raise RuntimeError(
            f"Report iteration mismatch: expected {iteration}, got {parsed} in {_rel_path(src)}"
        )


def _assert_task_iteration(*, src: Path, iteration: int) -> None:
    text = src.read_text(encoding="utf-8")
    match = _TASK_ITERATION_RE.search(text)
    if not match:
        raise RuntimeError(f"Missing task iteration marker in {_rel_path(src)}")
    parsed = int(match.group(1))
    if parsed != iteration:
        raise RuntimeError(
            f"Task iteration mismatch: expected {iteration}, got {parsed} in {_rel_path(src)}"
        )


def _assert_validation_results_iteration(*, src: Path, iteration: int) -> None:
    payload = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid validation results format: {_rel_path(src)}")
    for validator in PARALLEL_VALIDATORS:
        item = payload.get(validator)
        if not isinstance(item, dict):
            raise RuntimeError(f"Missing validator result {validator} in {_rel_path(src)}")
        result_iteration = item.get("iteration")
        if result_iteration != iteration:
            raise RuntimeError(
                "Validation result iteration mismatch: "
                f"expected {iteration}, got {result_iteration!r} in {_rel_path(src)}#{validator}"
            )


def _assert_validator_report_iteration(*, src: Path, iteration: int, validator: str) -> None:
    payload = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid validator report format: {_rel_path(src)}")
    parsed_validator = payload.get("validator")
    if parsed_validator != validator:
        raise RuntimeError(
            f"Validator name mismatch in {_rel_path(src)}: expected {validator}, got {parsed_validator!r}"
        )
    parsed_iteration = payload.get("iteration")
    if parsed_iteration != iteration:
        raise RuntimeError(
            "Validator report iteration mismatch: "
            f"expected {iteration}, got {parsed_iteration!r} in {_rel_path(src)}"
        )


def _backup_iteration_artifacts(*, iteration: int, stage: str) -> Path | None:
    """
    将当前迭代的所有产物备份到 iterations/iter_{N}/ 目录。
    返回备份目录路径，如果没有任何文件可备份则返回 None。
    """
    if stage not in {"IMPLEMENTER", "VALIDATE"}:
        raise ValueError(f"Unsupported archive stage: {stage!r}")

    dest_dir = ITERATION_ARCHIVE_DIR / f"iter_{iteration}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0

    # 1. 复制 reports 目录下的当前报告文件
    if stage == "IMPLEMENTER":
        report_files = [
            REPORT_IMPLEMENTER_FILE,
            REPORT_MAIN_DECISION_FILE,
            REPORT_ITERATION_SUMMARY_FILE,
        ]
    else:
        report_files = [
            SYNTHESIZER_REPORT_FILE,
            VALIDATION_RESULTS_FILE,
            REPORT_MAIN_DECISION_FILE,
        ]

    for src in report_files:
        if not (src.exists() and src.stat().st_size > 0):
            continue
        if src == REPORT_ITERATION_SUMMARY_FILE:
            if not _summary_matches_iteration(summary_file=src, iteration=iteration):
                raise RuntimeError(
                    f"Stale summary detected for iteration {iteration}: {_rel_path(src)}"
                )
        elif src == REPORT_IMPLEMENTER_FILE:
            _assert_markdown_iteration(src=src, iteration=iteration)
        elif src == SYNTHESIZER_REPORT_FILE:
            _assert_markdown_iteration(src=src, iteration=iteration)
        elif src == VALIDATION_RESULTS_FILE:
            _assert_validation_results_iteration(src=src, iteration=iteration)
        shutil.copy2(src, dest_dir / src.name)
        copied += 1

    # 2. 复制验证器报告
    if stage == "VALIDATE" and VALIDATOR_REPORTS_DIR.exists():
        dest_validators = dest_dir / "report_validators"
        dest_validators.mkdir(exist_ok=True)
        for f in VALIDATOR_REPORTS_DIR.iterdir():
            if f.is_file() and f.suffix == ".md" and f.name != ".gitkeep":
                validator = f.stem.upper()
                _assert_validator_report_iteration(src=f, iteration=iteration, validator=validator)
                shutil.copy2(f, dest_validators / f.name)
                copied += 1

    # 3. 复制工单文件
    dest_workspace = dest_dir / "workspace"
    # IMPLEMENTER 工单
    if stage == "IMPLEMENTER" and IMPLEMENTER_TASK_FILE.exists() and IMPLEMENTER_TASK_FILE.stat().st_size > 0:
        _assert_task_iteration(src=IMPLEMENTER_TASK_FILE, iteration=iteration)
        dest_workspace.mkdir(parents=True, exist_ok=True)
        shutil.copy2(IMPLEMENTER_TASK_FILE, dest_workspace / "implementer_task.md")
        copied += 1
    # 验证器工单
    if stage == "VALIDATE" and VALIDATOR_WORKSPACE_DIR.exists():
        dest_val_ws = dest_workspace / "validators"
        dest_val_ws.mkdir(parents=True, exist_ok=True)
        for f in VALIDATOR_WORKSPACE_DIR.iterdir():
            if f.is_file() and f.suffix == ".md" and f.name != ".gitkeep":
                shutil.copy2(f, dest_val_ws / f.name)
                copied += 1

    if copied == 0:
        shutil.rmtree(dest_dir, ignore_errors=True)
        return None

    _append_log_line(
        f"orchestrator: iteration {iteration} artifacts archived to {_rel_path(dest_dir)} ({copied} files)\n"
    )
    return dest_dir


def _clear_iteration_archives() -> int:
    """删除所有迭代归档目录，返回删除的迭代数。"""
    if not ITERATION_ARCHIVE_DIR.exists():
        return 0
    count = 0
    for d in sorted(ITERATION_ARCHIVE_DIR.iterdir()):
        if d.is_dir() and d.name.startswith("iter_"):
            shutil.rmtree(d, ignore_errors=True)
            count += 1
    return count
