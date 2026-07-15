from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from src.mission_context import MissionContext
from src.state_machine import FailureCode, MissionState


class FailsafeLevel(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class FailsafeAction(str, Enum):
    CONTINUE = "CONTINUE"
    WARN = "WARN"
    RTL = "RTL"
    LAND = "LAND"
    ABORT = "ABORT"


@dataclass(frozen=True, slots=True)
class FailsafeConfig:
    battery_warning_pct: float = 30.0
    battery_critical_pct: float = 20.0
    minimum_satellites: int = 6
    maximum_altitude_m: float = 120.0
    maximum_airspeed_m_s: float = 35.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.battery_critical_pct <= 100.0:
            raise ValueError("배터리 위험 임계값은 0~100%여야 합니다.")
        if not 0.0 <= self.battery_warning_pct <= 100.0:
            raise ValueError("배터리 경고 임계값은 0~100%여야 합니다.")
        if self.battery_critical_pct >= self.battery_warning_pct:
            raise ValueError("배터리 위험 임계값은 경고 임계값보다 낮아야 합니다.")
        if self.minimum_satellites < 0:
            raise ValueError("최소 위성 수는 0 이상이어야 합니다.")
        if self.maximum_altitude_m <= 0:
            raise ValueError("최대 고도는 0보다 커야 합니다.")
        if self.maximum_airspeed_m_s <= 0:
            raise ValueError("최대 속도는 0보다 커야 합니다.")


@dataclass(frozen=True, slots=True)
class FailsafeDecision:
    level: FailsafeLevel
    action: FailsafeAction
    failure_code: FailureCode
    reason: str

    @property
    def triggered(self) -> bool:
        return self.level is FailsafeLevel.CRITICAL


class FailsafeSupervisor:
    GOOD_GPS_FIXES = {
        "FIX_3D",
        "DGPS",
        "RTK_FLOAT",
        "RTK_FIXED",
    }

    GPS_REQUIRED_STATES = {
        MissionState.TAKEOFF,
        MissionState.HOVER,
        MissionState.FORWARD_TRANSITION,
        MissionState.CRUISE,
        MissionState.TARGET_SEARCH,
        MissionState.BACK_TRANSITION,
        MissionState.RETURN_HOME,
    }

    def __init__(self, config: FailsafeConfig | None = None) -> None:
        self.config = config or FailsafeConfig()
        self.last_decision = self._normal()

    @staticmethod
    def _normal() -> FailsafeDecision:
        return FailsafeDecision(
            level=FailsafeLevel.NORMAL,
            action=FailsafeAction.CONTINUE,
            failure_code=FailureCode.NONE,
            reason="정상",
        )

    def evaluate(
        self,
        context: MissionContext,
        state: MissionState,
    ) -> FailsafeDecision:
        if context.battery_remaining_pct <= self.config.battery_critical_pct:
            return FailsafeDecision(
                level=FailsafeLevel.CRITICAL,
                action=FailsafeAction.RTL,
                failure_code=FailureCode.LOW_BATTERY,
                reason=(
                    "배터리 잔량이 위험 임계값 이하입니다: "
                    f"{context.battery_remaining_pct:.1f}%"
                ),
            )

        if (
            state in self.GPS_REQUIRED_STATES
            and context.in_air
            and (
                context.gps_fix not in self.GOOD_GPS_FIXES
                or context.satellites < self.config.minimum_satellites
            )
        ):
            return FailsafeDecision(
                level=FailsafeLevel.CRITICAL,
                action=FailsafeAction.RTL,
                failure_code=FailureCode.GPS_LOST,
                reason=(
                    "비행 중 GPS 품질이 기준 미달입니다: "
                    f"fix={context.gps_fix}, satellites={context.satellites}"
                ),
            )

        if context.altitude_m > self.config.maximum_altitude_m:
            return FailsafeDecision(
                level=FailsafeLevel.CRITICAL,
                action=FailsafeAction.LAND,
                failure_code=FailureCode.ALTITUDE_LIMIT_EXCEEDED,
                reason=(
                    "최대 허용 고도를 초과했습니다: "
                    f"{context.altitude_m:.1f}m > "
                    f"{self.config.maximum_altitude_m:.1f}m"
                ),
            )

        if context.airspeed_m_s > self.config.maximum_airspeed_m_s:
            return FailsafeDecision(
                level=FailsafeLevel.CRITICAL,
                action=FailsafeAction.RTL,
                failure_code=FailureCode.AIRSPEED_LIMIT_EXCEEDED,
                reason=(
                    "최대 허용 속도를 초과했습니다: "
                    f"{context.airspeed_m_s:.1f}m/s > "
                    f"{self.config.maximum_airspeed_m_s:.1f}m/s"
                ),
            )

        if context.battery_remaining_pct <= self.config.battery_warning_pct:
            return FailsafeDecision(
                level=FailsafeLevel.WARNING,
                action=FailsafeAction.WARN,
                failure_code=FailureCode.NONE,
                reason=(
                    "배터리 잔량 경고: "
                    f"{context.battery_remaining_pct:.1f}%"
                ),
            )

        return self._normal()

    def apply(
        self,
        context: MissionContext,
        state: MissionState,
    ) -> FailsafeDecision:
        decision = self.evaluate(context, state)
        self.last_decision = decision

        context.failsafe_triggered = decision.triggered
        context.failsafe_code = decision.failure_code.name
        context.failsafe_reason = decision.reason
        context.failsafe_action = decision.action.value

        return decision
