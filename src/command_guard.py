from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.mission_context import MissionContext
from src.target_estimate import TargetEstimate


class GuardCode(str, Enum):
    OK = "OK"
    DISCONNECTED = "DISCONNECTED"
    NOT_IN_AIR = "NOT_IN_AIR"
    MISSION_NOT_RUNNING = "MISSION_NOT_RUNNING"
    MISSION_NOT_PAUSED = "MISSION_NOT_PAUSED"
    FAILSAFE_ACTIVE = "FAILSAFE_ACTIVE"
    WRONG_VTOL_STATE = "WRONG_VTOL_STATE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    TRACKING_UNSTABLE = "TRACKING_UNSTABLE"
    STALE_TARGET = "STALE_TARGET"
    TARGET_TOO_FAR = "TARGET_TOO_FAR"


@dataclass(frozen=True, slots=True)
class GuardResult:
    allowed: bool
    code: GuardCode
    reason: str


@dataclass(frozen=True, slots=True)
class CommandGuardConfig:
    minimum_confidence: float = 0.75
    maximum_target_age_s: float = 1.5
    maximum_target_distance_m: float = 80.0
    required_vtol_state: str = "MC"
    require_in_air: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError("최소 신뢰도는 0 이상 1 이하여야 합니다.")
        if self.maximum_target_age_s <= 0.0:
            raise ValueError("최대 표적 지연시간은 0보다 커야 합니다.")
        if self.maximum_target_distance_m <= 0.0:
            raise ValueError("최대 표적 거리는 0보다 커야 합니다.")
        if not self.required_vtol_state.strip():
            raise ValueError("필수 VTOL 상태는 비어 있을 수 없습니다.")


class CommandGuard:
    """Offboard 전환 전에 기체·임무·표적 조건을 검사한다."""

    def __init__(
        self,
        config: CommandGuardConfig | None = None,
    ) -> None:
        self.config = config or CommandGuardConfig()

    @staticmethod
    def _allow() -> GuardResult:
        return GuardResult(
            allowed=True,
            code=GuardCode.OK,
            reason="Offboard 전환 조건 충족",
        )

    @staticmethod
    def _deny(code: GuardCode, reason: str) -> GuardResult:
        return GuardResult(
            allowed=False,
            code=code,
            reason=reason,
        )

    def evaluate_target(
        self,
        target: TargetEstimate,
        now_s: float,
    ) -> GuardResult:
        if target.confidence < self.config.minimum_confidence:
            return self._deny(
                GuardCode.LOW_CONFIDENCE,
                "표적 탐지 신뢰도가 기준보다 낮습니다.",
            )

        if not target.tracking_stable:
            return self._deny(
                GuardCode.TRACKING_UNSTABLE,
                "표적 추적이 안정화되지 않았습니다.",
            )

        if target.age_s(now_s) > self.config.maximum_target_age_s:
            return self._deny(
                GuardCode.STALE_TARGET,
                "표적 추정값이 허용 지연시간을 초과했습니다.",
            )

        if (
            target.horizontal_distance_m
            > self.config.maximum_target_distance_m
        ):
            return self._deny(
                GuardCode.TARGET_TOO_FAR,
                "표적이 Offboard 접근 허용거리 밖에 있습니다.",
            )

        return self._allow()

    def evaluate_vehicle(
        self,
        context: MissionContext,
        *,
        require_mission_running: bool = True,
        require_mission_paused: bool = True,
        require_multicopter: bool = True,
    ) -> GuardResult:
        if not context.connected:
            return self._deny(
                GuardCode.DISCONNECTED,
                "비행제어기 연결이 끊어졌습니다.",
            )

        if self.config.require_in_air and not context.in_air:
            return self._deny(
                GuardCode.NOT_IN_AIR,
                "기체가 비행 중이 아닙니다.",
            )

        if context.failsafe_triggered:
            return self._deny(
                GuardCode.FAILSAFE_ACTIVE,
                "Failsafe가 활성화되어 있습니다.",
            )

        if require_mission_running and not context.mission_started:
            return self._deny(
                GuardCode.MISSION_NOT_RUNNING,
                "MissionRaw 임무가 실행 중이 아닙니다.",
            )

        if require_mission_paused and not context.mission_paused:
            return self._deny(
                GuardCode.MISSION_NOT_PAUSED,
                "MissionRaw 임무가 일시정지되지 않았습니다.",
            )

        if (
            require_multicopter
            and context.vtol_state != self.config.required_vtol_state
        ):
            return self._deny(
                GuardCode.WRONG_VTOL_STATE,
                "기체가 멀티콥터 상태가 아닙니다.",
            )

        return self._allow()

    def evaluate_offboard_entry(
        self,
        context: MissionContext,
        target: TargetEstimate,
        now_s: float,
    ) -> GuardResult:
        vehicle_result = self.evaluate_vehicle(context)
        if not vehicle_result.allowed:
            return vehicle_result

        return self.evaluate_target(target, now_s)
