from __future__ import annotations

from dataclasses import dataclass

from src.target_filter import (
    ConstantVelocityKalman2D,
    FilteredTargetEstimate,
    TargetFilterConfig,
    TargetMeasurement,
)


@dataclass(frozen=True, slots=True)
class OffboardTargetGate:
    """필터 추정값을 Offboard 접근에 사용할 수 있는지 판정한 결과."""

    allowed: bool
    reason: str


class FilteredTargetPipeline:
    """측정값·누락·예측을 통합해 안전한 표적 추정값을 제공한다."""

    def __init__(
        self,
        config: TargetFilterConfig | None = None,
        *,
        minimum_output_confidence: float = 0.35,
    ) -> None:
        if not 0.0 <= minimum_output_confidence <= 1.0:
            raise ValueError("출력 최소 신뢰도는 0 이상 1 이하여야 합니다.")

        self.filter = ConstantVelocityKalman2D(config)
        self.minimum_output_confidence = minimum_output_confidence

    def process(
        self,
        *,
        now_s: float,
        measurement: TargetMeasurement | None,
    ) -> FilteredTargetEstimate:
        if measurement is None:
            return self.filter.predict(now_s)

        return self.filter.update(
            measurement=measurement,
            now_s=now_s,
        )

    def check_offboard_target(
        self,
        estimate: FilteredTargetEstimate,
    ) -> OffboardTargetGate:
        if not estimate.initialized:
            return OffboardTargetGate(
                allowed=False,
                reason="표적 필터가 초기화되지 않았습니다.",
            )

        if estimate.stale:
            return OffboardTargetGate(
                allowed=False,
                reason="표적 추정값이 오래되었습니다.",
            )

        if not estimate.tracking_stable:
            return OffboardTargetGate(
                allowed=False,
                reason="표적 추적이 안정화되지 않았습니다.",
            )

        if estimate.confidence < self.minimum_output_confidence:
            return OffboardTargetGate(
                allowed=False,
                reason="필터 출력 신뢰도가 기준보다 낮습니다.",
            )

        return OffboardTargetGate(
            allowed=True,
            reason="Offboard 접근에 사용할 수 있는 표적 추정값입니다.",
        )
