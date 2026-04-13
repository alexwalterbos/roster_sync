from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def record_automation_run(
    *,
    status_path: Path,
    history_path: Path,
    payload: dict[str, Any],
) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    status_path.write_text(
        json.dumps(payload, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")
