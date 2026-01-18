from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import (
    DEV_PLAN_FILE,
    DEV_PLAN_STAGED_FILE,
    MEMORY_BACKUP_DIR,
    REPORTS_BACKUP_DIR,
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
    收紧 dev_plan 写入接口：
    - MAIN 禁止直接修改 `memory/dev_plan.md`（禁止补丁/差分方式增量编辑）
    - 若需要变更 dev_plan，MAIN 必须整文件覆盖写入 `workspace/main/dev_plan_next.md`
    - 编排器在 MAIN 运行后验证、备份旧 dev_plan，然后原子覆盖到 `memory/dev_plan.md`
    """
    _validate_session_id(main_session_id)  # 关键变量：会话 id 必须合法
    _require_file(DEV_PLAN_FILE)  # 关键分支：dev_plan 必须存在
    after_hash = _sha256_text(_read_text(DEV_PLAN_FILE))  # 关键变量：运行后哈希
    if after_hash != dev_plan_before_hash:  # 关键分支：禁止直接修改 dev_plan
        raise RuntimeError(
            "MAIN must not modify `memory/dev_plan.md` directly. "
            f"Write the full next dev_plan to `{_rel_path(DEV_PLAN_STAGED_FILE)}` instead."
        )

    if not DEV_PLAN_STAGED_FILE.exists():  # 关键分支：没有草案则直接返回
        return

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
    _atomic_write_text(DEV_PLAN_FILE, staged + "\n")  # 关键变量：原子覆盖 dev_plan
    DEV_PLAN_STAGED_FILE.unlink()  # 关键变量：清理草案
    _append_log_line(
        "orchestrator: dev_plan_committed "
        f"backup={_rel_path(backed)}\n"
    )
