from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from src.mission_plan import MissionPlan
from src.mission_raw_builder import RawMissionItemData, build_raw_mission_items


@dataclass(frozen=True, slots=True)
class MissionItemMismatch:
    """업로드 원본과 FC에서 다시 받은 항목 간 차이."""

    seq: int
    field: str
    expected: object
    actual: object
    message: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        for key in ("expected", "actual"):
            value = data[key]
            if isinstance(value, float) and not math.isfinite(value):
                data[key] = str(value)
        return data


@dataclass(frozen=True, slots=True)
class MissionVerificationResult:
    """MissionRaw 업로드-다운로드 대조 결과."""

    matched: bool
    expected_count: int
    actual_count: int
    mismatches: tuple[MissionItemMismatch, ...]

    @property
    def mismatch_count(self) -> int:
        return len(self.mismatches)

    def to_dict(self) -> dict[str, object]:
        return {
            "matched": self.matched,
            "expected_count": self.expected_count,
            "actual_count": self.actual_count,
            "mismatch_count": self.mismatch_count,
            "mismatches": [item.to_dict() for item in self.mismatches],
        }


def _read_field(item: Any, field: str) -> object:
    if isinstance(item, dict):
        if field not in item:
            raise AttributeError(field)
        return item[field]

    if not hasattr(item, field):
        raise AttributeError(field)

    return getattr(item, field)


def _numbers_match(
    expected: float,
    actual: object,
    tolerance: float,
) -> bool:
    try:
        actual_value = float(actual)
    except (TypeError, ValueError):
        return False

    if math.isnan(expected):
        return math.isnan(actual_value)

    return math.isclose(
        expected,
        actual_value,
        rel_tol=0.0,
        abs_tol=tolerance,
    )


def verify_downloaded_mission(
    mission_plan: MissionPlan,
    downloaded_items: list[Any] | tuple[Any, ...],
    stop_hold_time_s: float = 1.0,
    float_tolerance: float = 1e-4,
    altitude_tolerance_m: float = 0.05,
) -> MissionVerificationResult:
    """MissionPlan과 FC에서 내려받은 MISSION_ITEM_INT 목록을 대조한다."""

    if float_tolerance < 0.0:
        raise ValueError("실수 허용오차는 0 이상이어야 합니다.")
    if altitude_tolerance_m < 0.0:
        raise ValueError("고도 허용오차는 0 이상이어야 합니다.")

    expected_items = build_raw_mission_items(
        mission_plan=mission_plan,
        stop_hold_time_s=stop_hold_time_s,
    )
    actual_items = tuple(downloaded_items)
    mismatches: list[MissionItemMismatch] = []

    if len(expected_items) != len(actual_items):
        mismatches.append(
            MissionItemMismatch(
                seq=-1,
                field="item_count",
                expected=len(expected_items),
                actual=len(actual_items),
                message="임무 항목 수가 다릅니다.",
            )
        )

    integer_fields = (
        "seq",
        "frame",
        "command",
        "current",
        "autocontinue",
        "x",
        "y",
        "mission_type",
    )
    float_fields = (
        "param1",
        "param2",
        "param3",
        "param4",
    )

    for index, expected in enumerate(expected_items[: len(actual_items)]):
        actual = actual_items[index]

        for field in integer_fields:
            expected_value = getattr(expected, field)
            try:
                actual_value = int(_read_field(actual, field))
            except (AttributeError, TypeError, ValueError):
                actual_value = None

            if expected_value != actual_value:
                mismatches.append(
                    MissionItemMismatch(
                        seq=expected.seq,
                        field=field,
                        expected=expected_value,
                        actual=actual_value,
                        message=f"{field} 값이 다릅니다.",
                    )
                )

        for field in float_fields:
            expected_value = float(getattr(expected, field))
            try:
                actual_value = _read_field(actual, field)
            except AttributeError:
                actual_value = None

            if not _numbers_match(
                expected=expected_value,
                actual=actual_value,
                tolerance=float_tolerance,
            ):
                mismatches.append(
                    MissionItemMismatch(
                        seq=expected.seq,
                        field=field,
                        expected=expected_value,
                        actual=actual_value,
                        message=f"{field} 값이 허용오차를 벗어났습니다.",
                    )
                )

        try:
            actual_altitude = _read_field(actual, "z")
        except AttributeError:
            actual_altitude = None

        if not _numbers_match(
            expected=float(expected.z),
            actual=actual_altitude,
            tolerance=altitude_tolerance_m,
        ):
            mismatches.append(
                MissionItemMismatch(
                    seq=expected.seq,
                    field="z",
                    expected=expected.z,
                    actual=actual_altitude,
                    message="상대고도가 허용오차를 벗어났습니다.",
                )
            )

    return MissionVerificationResult(
        matched=not mismatches,
        expected_count=len(expected_items),
        actual_count=len(actual_items),
        mismatches=tuple(mismatches),
    )
