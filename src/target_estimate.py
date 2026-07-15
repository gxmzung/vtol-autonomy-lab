from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TargetEstimate:
    """컴패니언 컴퓨터가 생성한 표적 상대 위치 추정값."""

    relative_north_m: float
    relative_east_m: float
    confidence: float
    tracking_stable: bool
    timestamp_s: float
    relative_down_m: float = 0.0
    source: str = "UNKNOWN"

    def __post_init__(self) -> None:
        numeric_values = (
            self.relative_north_m,
            self.relative_east_m,
            self.relative_down_m,
            self.confidence,
            self.timestamp_s,
        )

        if not all(math.isfinite(value) for value in numeric_values):
            raise ValueError("표적 추정값은 유한한 숫자여야 합니다.")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("표적 신뢰도는 0 이상 1 이하여야 합니다.")

        if self.timestamp_s < 0.0:
            raise ValueError("표적 추정 시각은 0 이상이어야 합니다.")

        source = self.source.strip()
        if not source:
            raise ValueError("표적 추정 출처는 비어 있을 수 없습니다.")

        object.__setattr__(self, "source", source)

    @property
    def horizontal_distance_m(self) -> float:
        return math.hypot(
            self.relative_north_m,
            self.relative_east_m,
        )

    @property
    def three_dimensional_distance_m(self) -> float:
        return math.sqrt(
            self.relative_north_m**2
            + self.relative_east_m**2
            + self.relative_down_m**2
        )

    @property
    def bearing_deg(self) -> float:
        if self.horizontal_distance_m == 0.0:
            return 0.0

        return (
            math.degrees(
                math.atan2(
                    self.relative_east_m,
                    self.relative_north_m,
                )
            )
            + 360.0
        ) % 360.0

    def age_s(self, now_s: float) -> float:
        if not math.isfinite(now_s):
            raise ValueError("현재 시각은 유한한 숫자여야 합니다.")
        return max(0.0, now_s - self.timestamp_s)

    def is_aligned(
        self,
        horizontal_tolerance_m: float,
        vertical_tolerance_m: float,
    ) -> bool:
        if horizontal_tolerance_m <= 0.0:
            raise ValueError("수평 허용오차는 0보다 커야 합니다.")
        if vertical_tolerance_m <= 0.0:
            raise ValueError("수직 허용오차는 0보다 커야 합니다.")

        return bool(
            self.horizontal_distance_m <= horizontal_tolerance_m
            and abs(self.relative_down_m) <= vertical_tolerance_m
        )
