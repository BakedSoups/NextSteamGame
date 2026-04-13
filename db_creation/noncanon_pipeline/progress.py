from __future__ import annotations

import atexit
import threading
import time


STAGE_ORDER = ("fetch", "filter", "sample", "semantics", "sqlite")
STAGE_LABELS = {
    "fetch": "fetch",
    "filter": "filter",
    "sample": "sample",
    "semantics": "semantics",
    "sqlite": "sqlite",
}

_LOCK = threading.Lock()
_STATE: dict[str, dict[str, str]] = {}
_TASK_IDS: dict[str, int] = {}
_REMOVE_AFTER_SECONDS = 2.0

try:
    from rich.console import Console
    from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn

    _RICH_AVAILABLE = True
    _CONSOLE = Console()
    _PROGRESS = Progress(
        TextColumn("{task.fields[appid]}", justify="right"),
        BarColumn(bar_width=24),
        TaskProgressColumn(),
        TextColumn("{task.fields[stage]}"),
        TextColumn("{task.fields[detail]}"),
        console=_CONSOLE,
        transient=False,
    )
    _PROGRESS.start()

    @atexit.register
    def _stop_progress() -> None:
        try:
            _PROGRESS.stop()
        except Exception:
            pass

    def _schedule_task_removal(appid: str | int) -> None:
        def _remove() -> None:
            time.sleep(_REMOVE_AFTER_SECONDS)
            with _LOCK:
                task_id = _TASK_IDS.pop(str(appid), None)
                _STATE.pop(str(appid), None)
            if task_id is not None:
                try:
                    _PROGRESS.remove_task(task_id)
                except Exception:
                    pass

        threading.Thread(target=_remove, daemon=True).start()

except Exception:
    _RICH_AVAILABLE = False
    _CONSOLE = None
    _PROGRESS = None


def _prefix(stage: str) -> str:
    return f"[{stage:<10}]"


def _render_stage_bar(appid: str | int) -> str:
    key = str(appid)
    item = _STATE.setdefault(key, {})
    cells = []
    for stage in STAGE_ORDER:
        status = item.get(stage, "pending")
        label = STAGE_LABELS[stage]
        if status == "done":
            cells.append(f"[x] {label}")
        elif status == "active":
            cells.append(f"[>] {label}")
        elif status == "skipped":
            cells.append(f"[-] {label}")
        else:
            cells.append(f"[ ] {label}")
    return " | ".join(cells)


def _ensure_rich_task(appid: str | int) -> int:
    key = str(appid)
    task_id = _TASK_IDS.get(key)
    if task_id is not None:
        return task_id
    task_id = _PROGRESS.add_task(
        "",
        total=len(STAGE_ORDER),
        completed=0,
        appid=f"appid={appid}",
        stage="starting",
        detail="",
    )
    _TASK_IDS[key] = task_id
    return task_id


def _rich_update(appid: str | int, *, completed: int, stage: str, detail: str) -> None:
    if not _RICH_AVAILABLE:
        return
    task_id = _ensure_rich_task(appid)
    _PROGRESS.update(
        task_id,
        completed=completed,
        stage=stage,
        detail=detail,
        refresh=True,
    )


def log_stage(stage: str, message: str, *, appid: str | int | None = None) -> None:
    if _RICH_AVAILABLE:
        if appid is None:
            _CONSOLE.print(f"{_prefix(stage)} {message}")
        else:
            _CONSOLE.print(f"{_prefix(stage)} appid={appid} {message}")
        return
    scope = f" appid={appid}" if appid is not None else ""
    print(f"{_prefix(stage)}{scope} {message}", flush=True)


def advance_appid(appid: str | int, stage: str, detail: str = "") -> None:
    with _LOCK:
        key = str(appid)
        item = _STATE.setdefault(key, {})
        completed = 0
        active_stage = stage
        for current_stage in STAGE_ORDER:
            if current_stage == stage:
                item[current_stage] = "done"
                completed += 1
                break
            if item.get(current_stage) in ("done", "skipped"):
                completed += 1
                continue
            item[current_stage] = "done"
            completed += 1
        next_index = STAGE_ORDER.index(stage) + 1
        if next_index < len(STAGE_ORDER):
            next_stage = STAGE_ORDER[next_index]
            if item.get(next_stage, "pending") == "pending":
                item[next_stage] = "active"
            active_stage = next_stage
        else:
            active_stage = "done"

        if _RICH_AVAILABLE:
            _rich_update(appid, completed=completed, stage=active_stage, detail=detail)
            return
        bar = _render_stage_bar(appid)
    suffix = f" :: {detail}" if detail else ""
    print(f"[progress  ] appid={appid} {bar}{suffix}", flush=True)


def complete_appid(appid: str | int, result: str = "completed", detail: str = "") -> None:
    with _LOCK:
        key = str(appid)
        item = _STATE.setdefault(key, {})
        for stage in STAGE_ORDER:
            item[stage] = "done"
        if _RICH_AVAILABLE:
            _rich_update(appid, completed=len(STAGE_ORDER), stage=result, detail=detail)
            _schedule_task_removal(appid)
            return
        bar = _render_stage_bar(appid)
    suffix = f" :: {detail}" if detail else ""
    print(f"[completed ] appid={appid} {bar} => {result}{suffix}", flush=True)


def fail_appid(appid: str | int, result: str, detail: str = "") -> None:
    with _LOCK:
        key = str(appid)
        item = _STATE.setdefault(key, {})
        completed = 0
        for stage in STAGE_ORDER:
            status = item.get(stage, "pending")
            if status == "done":
                completed += 1
            elif status == "active":
                item[stage] = "skipped"
                break
        if _RICH_AVAILABLE:
            _rich_update(appid, completed=completed, stage=result, detail=detail)
            _schedule_task_removal(appid)
            return
        bar = _render_stage_bar(appid)
    suffix = f" :: {detail}" if detail else ""
    print(f"[completed ] appid={appid} {bar} => {result}{suffix}", flush=True)


def start_appid(appid: str | int) -> None:
    with _LOCK:
        key = str(appid)
        item = {stage: "pending" for stage in STAGE_ORDER}
        item["fetch"] = "active"
        _STATE[key] = item
        if _RICH_AVAILABLE:
            _rich_update(appid, completed=0, stage="fetch", detail="starting")
            return
        bar = _render_stage_bar(appid)
    print(f"[progress  ] appid={appid} {bar} :: starting", flush=True)


def log_banner(message: str) -> None:
    rule = "=" * 72
    if _RICH_AVAILABLE:
        _CONSOLE.print(f"\n{rule}\n{message}\n{rule}")
        return
    print(f"\n{rule}\n{message}\n{rule}", flush=True)
