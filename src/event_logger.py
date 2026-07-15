from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from src.state_machine import TransitionRecord


def write_transition_log(
    records: Iterable[TransitionRecord],
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "timestamp_s",
                "previous_state",
                "current_state",
                "reason",
                "failure_code",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "timestamp_s": f"{record.timestamp_s:.2f}",
                    "previous_state": record.previous_state.name,
                    "current_state": record.current_state.name,
                    "reason": record.reason,
                    "failure_code": record.failure_code.name,
                }
            )
    return path


def write_telemetry_log(
    rows: Iterable[dict[str, object]],
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows_list = list(rows)
    if not rows_list:
        raise ValueError("저장할 텔레메트리 데이터가 없습니다.")
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows_list[0].keys()))
        writer.writeheader()
        writer.writerows(rows_list)
    return path
