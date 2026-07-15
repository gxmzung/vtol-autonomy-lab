from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TargetMeasurement:
    """센서 또는 비전 계층에서 들어오는 표적 상대 위치 측정값."""

    timestamp_s: float
    north_m: float
    east_m: float
    confidence: float
    valid: bool = True

    def __post_init__(self) -> None:
        values = (
            self.timestamp_s,
            self.north_m,
            self.east_m,
            self.confidence,
        )

        if not all(math.isfinite(value) for value in values):
            raise ValueError("표적 측정값은 유한한 숫자여야 합니다.")

        if self.timestamp_s < 0.0:
            raise ValueError("측정 시각은 0 이상이어야 합니다.")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("신뢰도는 0 이상 1 이하여야 합니다.")


@dataclass(frozen=True, slots=True)
class TargetFilterConfig:
    """2차원 등속도 칼만필터와 안전 판정 설정."""

    process_accel_std_m_s2: float = 1.5
    measurement_std_m: float = 2.0
    initial_position_std_m: float = 8.0
    initial_velocity_std_m_s: float = 5.0

    min_measurement_confidence: float = 0.60
    innovation_gate_sigma: float = 4.0

    stable_position_std_m: float = 2.5
    stable_after_accepted_count: int = 3

    max_measurement_age_s: float = 1.0
    max_prediction_s: float = 1.5

    def __post_init__(self) -> None:
        positive_values = (
            self.process_accel_std_m_s2,
            self.measurement_std_m,
            self.initial_position_std_m,
            self.initial_velocity_std_m_s,
            self.innovation_gate_sigma,
            self.stable_position_std_m,
            self.max_measurement_age_s,
            self.max_prediction_s,
        )

        if any(value <= 0.0 for value in positive_values):
            raise ValueError("필터 설정의 표준편차와 시간 제한은 0보다 커야 합니다.")

        if not 0.0 <= self.min_measurement_confidence <= 1.0:
            raise ValueError("최소 측정 신뢰도는 0 이상 1 이하여야 합니다.")

        if self.stable_after_accepted_count < 1:
            raise ValueError("안정 판정에 필요한 측정 횟수는 1 이상이어야 합니다.")


@dataclass(frozen=True, slots=True)
class FilteredTargetEstimate:
    """필터가 출력하는 표적 위치·속도·불확실성."""

    timestamp_s: float

    north_m: float
    east_m: float

    velocity_north_m_s: float
    velocity_east_m_s: float

    position_std_north_m: float
    position_std_east_m: float

    confidence: float
    tracking_stable: bool

    initialized: bool
    measurement_accepted: bool
    prediction_only: bool
    stale: bool

    innovation_distance: float | None = None


class _AxisKalmanFilter:
    """한 축의 위치·속도를 추정하는 2상태 칼만필터."""

    def __init__(
        self,
        initial_position_std_m: float,
        initial_velocity_std_m_s: float,
    ) -> None:
        self.position_m = 0.0
        self.velocity_m_s = 0.0

        self.p00 = initial_position_std_m ** 2
        self.p01 = 0.0
        self.p10 = 0.0
        self.p11 = initial_velocity_std_m_s ** 2

    def predict(
        self,
        dt_s: float,
        process_accel_std_m_s2: float,
    ) -> None:
        self.position_m += self.velocity_m_s * dt_s

        old_p00 = self.p00
        old_p01 = self.p01
        old_p10 = self.p10
        old_p11 = self.p11

        q = process_accel_std_m_s2 ** 2
        dt2 = dt_s ** 2
        dt3 = dt_s ** 3
        dt4 = dt_s ** 4

        q00 = 0.25 * dt4 * q
        q01 = 0.5 * dt3 * q
        q11 = dt2 * q

        self.p00 = (
            old_p00
            + dt_s * old_p10
            + dt_s * old_p01
            + dt2 * old_p11
            + q00
        )
        self.p01 = old_p01 + dt_s * old_p11 + q01
        self.p10 = old_p10 + dt_s * old_p11 + q01
        self.p11 = old_p11 + q11

    def innovation(
        self,
        measurement_m: float,
        measurement_variance_m2: float,
    ) -> tuple[float, float]:
        residual = measurement_m - self.position_m
        innovation_variance = self.p00 + measurement_variance_m2
        return residual, innovation_variance

    def update(
        self,
        measurement_m: float,
        measurement_variance_m2: float,
    ) -> None:
        residual, innovation_variance = self.innovation(
            measurement_m,
            measurement_variance_m2,
        )

        k0 = self.p00 / innovation_variance
        k1 = self.p10 / innovation_variance

        old_p00 = self.p00
        old_p01 = self.p01
        old_p10 = self.p10
        old_p11 = self.p11

        self.position_m += k0 * residual
        self.velocity_m_s += k1 * residual

        self.p00 = max(0.0, (1.0 - k0) * old_p00)
        self.p01 = (1.0 - k0) * old_p01
        self.p10 = old_p10 - k1 * old_p00
        self.p11 = max(0.0, old_p11 - k1 * old_p01)


class ConstantVelocityKalman2D:
    """북·동 상대좌표를 등속도 모델로 추정하는 경량 칼만필터."""

    def __init__(
        self,
        config: TargetFilterConfig | None = None,
    ) -> None:
        self.config = config or TargetFilterConfig()
        self.reset()

    def reset(self) -> None:
        self._north = _AxisKalmanFilter(
            initial_position_std_m=self.config.initial_position_std_m,
            initial_velocity_std_m_s=self.config.initial_velocity_std_m_s,
        )
        self._east = _AxisKalmanFilter(
            initial_position_std_m=self.config.initial_position_std_m,
            initial_velocity_std_m_s=self.config.initial_velocity_std_m_s,
        )

        self._initialized = False
        self._timestamp_s: float | None = None
        self._last_accepted_measurement_s: float | None = None
        self._accepted_count = 0
        self._last_measurement_confidence = 0.0

    @property
    def initialized(self) -> bool:
        return self._initialized

    def _initialize(
        self,
        measurement: TargetMeasurement,
    ) -> FilteredTargetEstimate:
        self._north.position_m = measurement.north_m
        self._east.position_m = measurement.east_m

        self._timestamp_s = measurement.timestamp_s
        self._last_accepted_measurement_s = measurement.timestamp_s
        self._last_measurement_confidence = measurement.confidence
        self._accepted_count = 1
        self._initialized = True

        return self._build_estimate(
            now_s=measurement.timestamp_s,
            measurement_accepted=True,
            prediction_only=False,
            stale=False,
            innovation_distance=0.0,
        )

    def _predict_to(
        self,
        now_s: float,
    ) -> None:
        if not self._initialized:
            return

        assert self._timestamp_s is not None

        if now_s < self._timestamp_s:
            raise ValueError("필터 시각은 이전 시각으로 되돌아갈 수 없습니다.")

        dt_s = now_s - self._timestamp_s

        if dt_s <= 0.0:
            return

        self._north.predict(
            dt_s=dt_s,
            process_accel_std_m_s2=self.config.process_accel_std_m_s2,
        )
        self._east.predict(
            dt_s=dt_s,
            process_accel_std_m_s2=self.config.process_accel_std_m_s2,
        )
        self._timestamp_s = now_s

    def update(
        self,
        measurement: TargetMeasurement,
        now_s: float | None = None,
    ) -> FilteredTargetEstimate:
        evaluation_time_s = (
            measurement.timestamp_s
            if now_s is None
            else now_s
        )

        if not math.isfinite(evaluation_time_s):
            raise ValueError("현재 시각은 유한한 숫자여야 합니다.")

        if evaluation_time_s < measurement.timestamp_s:
            raise ValueError("현재 시각은 측정 시각보다 빠를 수 없습니다.")

        if self._timestamp_s is not None and measurement.timestamp_s < self._timestamp_s:
            raise ValueError("시간순서가 뒤바뀐 측정값은 처리할 수 없습니다.")

        age_s = evaluation_time_s - measurement.timestamp_s

        usable_measurement = (
            measurement.valid
            and measurement.confidence
            >= self.config.min_measurement_confidence
            and age_s <= self.config.max_measurement_age_s
        )

        if not self._initialized:
            if not usable_measurement:
                return self._empty_estimate(
                    now_s=evaluation_time_s,
                    stale=age_s > self.config.max_measurement_age_s,
                )

            estimate = self._initialize(measurement)
            if evaluation_time_s > measurement.timestamp_s:
                return self.predict(evaluation_time_s)
            return estimate

        self._predict_to(measurement.timestamp_s)

        if not usable_measurement:
            if evaluation_time_s > measurement.timestamp_s:
                self._predict_to(evaluation_time_s)

            stale = self._is_stale(evaluation_time_s)

            return self._build_estimate(
                now_s=evaluation_time_s,
                measurement_accepted=False,
                prediction_only=True,
                stale=stale,
                innovation_distance=None,
            )

        confidence_scale = max(
            measurement.confidence,
            self.config.min_measurement_confidence,
        )
        measurement_variance_m2 = (
            self.config.measurement_std_m / confidence_scale
        ) ** 2

        residual_n, innovation_variance_n = self._north.innovation(
            measurement.north_m,
            measurement_variance_m2,
        )
        residual_e, innovation_variance_e = self._east.innovation(
            measurement.east_m,
            measurement_variance_m2,
        )

        innovation_distance = math.sqrt(
            (residual_n ** 2) / innovation_variance_n
            + (residual_e ** 2) / innovation_variance_e
        )

        accepted = (
            innovation_distance
            <= self.config.innovation_gate_sigma
        )

        if accepted:
            self._north.update(
                measurement.north_m,
                measurement_variance_m2,
            )
            self._east.update(
                measurement.east_m,
                measurement_variance_m2,
            )

            self._last_accepted_measurement_s = measurement.timestamp_s
            self._last_measurement_confidence = measurement.confidence
            self._accepted_count += 1

        if evaluation_time_s > measurement.timestamp_s:
            self._predict_to(evaluation_time_s)

        stale = self._is_stale(evaluation_time_s)

        return self._build_estimate(
            now_s=evaluation_time_s,
            measurement_accepted=accepted,
            prediction_only=not accepted,
            stale=stale,
            innovation_distance=innovation_distance,
        )

    def predict(
        self,
        now_s: float,
    ) -> FilteredTargetEstimate:
        if not math.isfinite(now_s):
            raise ValueError("예측 시각은 유한한 숫자여야 합니다.")

        if not self._initialized:
            return self._empty_estimate(
                now_s=now_s,
                stale=True,
            )

        self._predict_to(now_s)
        stale = self._is_stale(now_s)

        return self._build_estimate(
            now_s=now_s,
            measurement_accepted=False,
            prediction_only=True,
            stale=stale,
            innovation_distance=None,
        )

    def _is_stale(self, now_s: float) -> bool:
        if self._last_accepted_measurement_s is None:
            return True

        return (
            now_s - self._last_accepted_measurement_s
            > self.config.max_prediction_s
        )

    def _build_estimate(
        self,
        now_s: float,
        measurement_accepted: bool,
        prediction_only: bool,
        stale: bool,
        innovation_distance: float | None,
    ) -> FilteredTargetEstimate:
        std_n = math.sqrt(max(0.0, self._north.p00))
        std_e = math.sqrt(max(0.0, self._east.p00))

        uncertainty_scale = max(std_n, std_e)
        uncertainty_factor = 1.0 / (
            1.0
            + uncertainty_scale
            / self.config.stable_position_std_m
        )

        confidence = max(
            0.0,
            min(
                1.0,
                self._last_measurement_confidence
                * uncertainty_factor,
            ),
        )

        tracking_stable = (
            self._accepted_count
            >= self.config.stable_after_accepted_count
            and std_n <= self.config.stable_position_std_m
            and std_e <= self.config.stable_position_std_m
            and not stale
        )

        return FilteredTargetEstimate(
            timestamp_s=now_s,
            north_m=self._north.position_m,
            east_m=self._east.position_m,
            velocity_north_m_s=self._north.velocity_m_s,
            velocity_east_m_s=self._east.velocity_m_s,
            position_std_north_m=std_n,
            position_std_east_m=std_e,
            confidence=confidence,
            tracking_stable=tracking_stable,
            initialized=True,
            measurement_accepted=measurement_accepted,
            prediction_only=prediction_only,
            stale=stale,
            innovation_distance=innovation_distance,
        )

    @staticmethod
    def _empty_estimate(
        now_s: float,
        stale: bool,
    ) -> FilteredTargetEstimate:
        return FilteredTargetEstimate(
            timestamp_s=now_s,
            north_m=0.0,
            east_m=0.0,
            velocity_north_m_s=0.0,
            velocity_east_m_s=0.0,
            position_std_north_m=math.inf,
            position_std_east_m=math.inf,
            confidence=0.0,
            tracking_stable=False,
            initialized=False,
            measurement_accepted=False,
            prediction_only=True,
            stale=stale,
            innovation_distance=None,
        )
