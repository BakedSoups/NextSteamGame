from __future__ import annotations

import atexit
import threading
import time
from typing import Dict, Optional

from rich.console import Console, Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text

STAGES = ("fetch", "filter", "sample", "semantics", "sqlite")
STAGE_INDEX = {stage: index for index, stage in enumerate(STAGES)}
REMOVE_DELAY_SECONDS = 2.0

_console = Console()
_progress = Progress(
    SpinnerColumn(),
    TextColumn("[bold]{task.fields[appid]}[/bold]"),
    BarColumn(bar_width=24),
    TextColumn("{task.completed}/{task.total}"),
    TextColumn("{task.fields[stage]}"),
    TextColumn("{task.fields[detail]}"),
    TimeElapsedColumn(),
    console=_console,
    transient=False,
)

_lock = threading.RLock()
_tasks: Dict[str, TaskID] = {}
_status_message = Text("")


def _render_layout() -> Group:
    return Group(_status_message, _progress)


_live = Live(
    _render_layout(),
    console=_console,
    transient=False,
    refresh_per_second=10,
)
_live.start()


def _render_appid(appid: str | int) -> str:
    return f"appid={appid}"


def _get_or_create_task(appid: str | int, detail: str = "") -> TaskID:
    appid_key = str(appid)
    with _lock:
        existing = _tasks.get(appid_key)
        if existing is not None:
            return existing

        task_id = _progress.add_task(
            "",
            total=len(STAGES),
            completed=0,
            appid=_render_appid(appid),
            stage="queued",
            detail=detail,
        )
        _tasks[appid_key] = task_id
        return task_id


def _set_stage(appid: str | int, stage: str, detail: str = "", completed: Optional[int] = None) -> None:
    task_id = _get_or_create_task(appid, detail=detail)
    update_kwargs = {
        "stage": stage,
        "detail": detail,
        "refresh": True,
    }
    if completed is not None:
        update_kwargs["completed"] = completed
    with _lock:
        _progress.update(task_id, **update_kwargs)
        _live.update(_render_layout(), refresh=True)


def _schedule_removal(appid: str | int) -> None:
    appid_key = str(appid)

    def _remove_later() -> None:
        time.sleep(REMOVE_DELAY_SECONDS)
        with _lock:
            task_id = _tasks.pop(appid_key, None)
            if task_id is not None:
                _progress.remove_task(task_id)
                _live.update(_render_layout(), refresh=True)

    thread = threading.Thread(target=_remove_later, daemon=True)
    thread.start()


def log_banner(message: str) -> None:
    with _lock:
        _console.print(f"[bold cyan]{message}[/bold cyan]")


def update_status(detail: str) -> None:
    global _status_message
    with _lock:
        _status_message = Text(detail, style="cyan")
        _live.update(_render_layout(), refresh=True)


def start_appid(appid: str | int, detail: str = "starting") -> None:
    _get_or_create_task(appid, detail=detail)
    _set_stage(appid, "queued", detail=detail, completed=0)


def log_stage(stage: str, appid: str | int | None = None, detail: str = "") -> None:
    if detail == "" and isinstance(appid, str) and not appid.strip().isdigit():
        detail = appid
        appid = None

    if appid is None:
        with _lock:
            _console.print(f"[cyan][{stage:<10}][/cyan] {detail}")
            _live.update(_render_layout(), refresh=True)
        return

    appid_str = str(appid)
    if stage in STAGE_INDEX:
        completed = STAGE_INDEX[stage]
        _set_stage(appid_str, stage, detail=detail, completed=completed)
        return

    _set_stage(appid_str, stage, detail=detail)


def advance_appid(appid: str | int, stage: str, detail: str = "") -> None:
    if stage not in STAGE_INDEX:
        raise ValueError(f"Unknown stage: {stage}")

    completed = STAGE_INDEX[stage] + 1
    _set_stage(appid, stage, detail=detail, completed=completed)


def complete_appid(appid: str | int, detail: str = "completed") -> None:
    task_id = _get_or_create_task(appid, detail=detail)
    with _lock:
        _progress.update(
            task_id,
            completed=len(STAGES),
            stage="completed",
            detail=detail,
            refresh=True,
        )
        _live.update(_render_layout(), refresh=True)
    _schedule_removal(appid)


def fail_appid(appid: str | int, detail: str = "error") -> None:
    task_id = _get_or_create_task(appid, detail=detail)
    with _lock:
        _progress.update(
            task_id,
            stage="error",
            detail=detail,
            refresh=True,
        )
        _live.update(_render_layout(), refresh=True)
    _schedule_removal(appid)


@atexit.register
def _stop_progress() -> None:
    with _lock:
        try:
            _live.stop()
        except Exception:
            pass
