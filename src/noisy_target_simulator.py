from __future__ import annotations

import math
import random
from dataclasses import dataclass

from src.target_filter import TargetMeasurement


@dataclass(frozen=True, slots=True)
class TrueTargetState:
    """가상 표적의 실제 상대 위치와 이동속도."""

    timestamp_s: float
    north_m: float
    east_m: float
    velocity_north_m_s: float
    velocity_east_m_s: float


class NoisyTargetSimulator:
    """노이즈·누락·이상치를 포함한 재현 가능한 표적 측정 생성기."""

    def __init__(
        self,
        *,
        initial_north_m: float = 20.0,
        initial_east_m: float = -5.0,
        velocity_north_m_s: float = -1.0,
        velocity_east_m_s: float = 0.25,
        measurement_std_m: float = 1.5,
        dropout_probability: float = 0.0,
        outlier_probability: float = 0.0,
        outlier_magnitude_m: float = 30.0,
        seed: int = 7,
    ) -> None:
        finite_values = (
            initial_north_m,
            initial_east_m,
            velocity_north_m_s,
            velocity_east_m_s,
            measurement_std_m,
            dropout_probability,
            outlier_probability,
            outlier_magnitude_m,
        )

        if not all(math.isfinite(value) for value in finite_values):
            raise ValueError("시뮬레이터 설정은 유한한 숫자여야 합니다.")

        if measurement_std_m < 0.0:
            raise ValueError("측정 노이즈 표준편차는 0 이상이어야 합니다.")

        if not 0.0 <= dropout_probability <= 1.0:
            raise ValueError("누락 확률은 0 이상 1 이하여야 합니다.")

        if not 0.0 <= outlier_probability <= 1.0:
            raise ValueError("이상치 확률은 0 이상 1 이하여야 합니다.")

        if outlier_magnitude_m < 0.0:
            raise ValueError("이상치 크기는 0 이상이어야 합니다.")

        self._north_m = initial_north_m
        self._east_m = initial_east_m
        self._velocity_north_m_s = velocity_north_m_s
        self._velocity_east_m_s = velocity_east_m_s
        self._timestamp_s = 0.0

        self.measurement_std_m = measurement_std_m
        self.dropout_probability = dropout_probability
        self.outlier_probability = outlier_probability
        self.outlier_magnitude_m = outlier_magnitude_m

        self._random = random.Random(seed)

    @property
    def true_state(self) -> TrueTargetState:
        return TrueTargetState(
            timestamp_s=self._timestamp_s,
            north_m=self._north_m,
            east_m=self._east_m,
            velocity_north_m_s=self._velocity_north_m_s,
            velocity_east_m_s=self._velocity_east_m_s,
        )

    def step(
        self,
        dt_s: float,
        *,
        force_dropout: bool = False,
        force_outlier: bool = False,
        confidence: float = 0.90,
    ) -> tuple[TrueTargetState, TargetMeasurement | None]:
        if not math.isfinite(dt_s) or dt_s <= 0.0:
            raise ValueError("시뮬레이션 간격은 0보다 큰 유한한 값이어야 합니다.")

        if not 0.0 <= confidence <= 1.0:
            raise ValueError("신뢰도는 0 이상 1 이하여야 합니다.")

        self._timestamp_s += dt_s
        self._north_m += self._velocity_north_m_s * dt_s
        self._east_m += self._velocity_east_m_s * dt_s

        state = self.true_state

        dropout = (
            force_dropout
            or self._random.random() < self.dropout_probability
        )

        if dropout:
            return state, None

        measured_north_m = (
            self._north_m
            + self._random.gauss(0.0, self.measurement_std_m)
        )
        measured_east_m = (
            self._east_m
            + self._random.gauss(0.0, self.measurement_std_m)
        )

        outlier = (
            force_outlier
            or self._random.random() < self.outlier_probability
        )

        if outlier:
            measured_north_m += self.outlier_magnitude_m
            measured_east_m -= self.outlier_magnitude_m

        measurement = TargetMeasurement(
            timestamp_s=self._timestamp_s,
            north_m=measured_north_m,
            east_m=measured_east_m,
            confidence=confidence,
            valid=True,
        )

        return state, measurement
