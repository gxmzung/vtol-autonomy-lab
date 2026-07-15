from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from src.mission_context import MissionContext


class MissionState(Enum):
    IDLE = auto()
    PREFLIGHT = auto()
    ARMING = auto()
    TAKEOFF = auto()
    HOVER = auto()
    FORWARD_TRANSITION = auto()
    CRUISE = auto()
    TARGET_SEARCH = auto()
    BACK_TRANSITION = auto()
    RETURN_HOME = auto()
    LAND = auto()
    COMPLETE = auto()
    ABORT = auto()


class FailureCode(Enum):
    NONE = auto()
    CONNECTION_LOST = auto()
    EXTERNAL_FAILSAFE = auto()

    LOW_BATTERY = auto()
    GPS_LOST = auto()
    ALTITUDE_LIMIT_EXCEEDED = auto()
    AIRSPEED_LIMIT_EXCEEDED = auto()

    PREFLIGHT_TIMEOUT = auto()
    ARMING_TIMEOUT = auto()
    TAKEOFF_TIMEOUT = auto()
    HOVER_TIMEOUT = auto()
    FORWARD_TRANSITION_TIMEOUT = auto()
    CRUISE_TIMEOUT = auto()
    TARGET_SEARCH_TIMEOUT = auto()
    BACK_TRANSITION_TIMEOUT = auto()
    RETURN_HOME_TIMEOUT = auto()
    LAND_TIMEOUT = auto()


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    timestamp_s: float
    previous_state: MissionState
    current_state: MissionState
    reason: str
    failure_code: FailureCode = FailureCode.NONE


class MissionStateMachine:
    DEFAULT_TIMEOUTS: dict[MissionState, float] = {
        MissionState.PREFLIGHT: 5.0,
        MissionState.ARMING: 5.0,
        MissionState.TAKEOFF: 12.0,
        MissionState.HOVER: 4.0,
        MissionState.FORWARD_TRANSITION: 8.0,
        MissionState.CRUISE: 20.0,
        MissionState.TARGET_SEARCH: 12.0,
        MissionState.BACK_TRANSITION: 8.0,
        MissionState.RETURN_HOME: 20.0,
        MissionState.LAND: 12.0,
    }

    TIMEOUT_FAILURE_CODES: dict[MissionState, FailureCode] = {
        MissionState.PREFLIGHT: FailureCode.PREFLIGHT_TIMEOUT,
        MissionState.ARMING: FailureCode.ARMING_TIMEOUT,
        MissionState.TAKEOFF: FailureCode.TAKEOFF_TIMEOUT,
        MissionState.HOVER: FailureCode.HOVER_TIMEOUT,
        MissionState.FORWARD_TRANSITION: FailureCode.FORWARD_TRANSITION_TIMEOUT,
        MissionState.CRUISE: FailureCode.CRUISE_TIMEOUT,
        MissionState.TARGET_SEARCH: FailureCode.TARGET_SEARCH_TIMEOUT,
        MissionState.BACK_TRANSITION: FailureCode.BACK_TRANSITION_TIMEOUT,
        MissionState.RETURN_HOME: FailureCode.RETURN_HOME_TIMEOUT,
        MissionState.LAND: FailureCode.LAND_TIMEOUT,
    }

    def __init__(
        self,
        takeoff_altitude_m: float = 10.0,
        timeouts: dict[MissionState, float] | None = None,
    ) -> None:
        if takeoff_altitude_m <= 0:
            raise ValueError("이륙 고도는 0보다 커야 합니다.")

        self.takeoff_altitude_m = takeoff_altitude_m
        self.timeouts = dict(self.DEFAULT_TIMEOUTS)

        if timeouts:
            self.timeouts.update(timeouts)

        self.state = MissionState.IDLE
        self.state_entered_at_s = 0.0
        self.failure_code = FailureCode.NONE
        self.history: list[TransitionRecord] = []

    def state_elapsed(self, now_s: float) -> float:
        return max(0.0, now_s - self.state_entered_at_s)

    def _transition(
        self,
        new_state: MissionState,
        now_s: float,
        reason: str,
        failure_code: FailureCode = FailureCode.NONE,
    ) -> None:
        previous_state = self.state
        self.state = new_state
        self.state_entered_at_s = now_s
        self.failure_code = failure_code

        self.history.append(
            TransitionRecord(
                timestamp_s=now_s,
                previous_state=previous_state,
                current_state=new_state,
                reason=reason,
                failure_code=failure_code,
            )
        )

    def _abort(
        self,
        now_s: float,
        reason: str,
        failure_code: FailureCode,
    ) -> None:
        self._transition(
            new_state=MissionState.ABORT,
            now_s=now_s,
            reason=reason,
            failure_code=failure_code,
        )

    def _check_timeout(self, now_s: float) -> bool:
        timeout_s = self.timeouts.get(self.state)

        if timeout_s is None:
            return False

        if self.state_elapsed(now_s) <= timeout_s:
            return False

        failure_code = self.TIMEOUT_FAILURE_CODES[self.state]
        self._abort(
            now_s=now_s,
            reason=f"{self.state.name} 상태가 {timeout_s:.1f}초를 초과했습니다.",
            failure_code=failure_code,
        )
        return True

    @staticmethod
    def _resolve_failsafe_code(code_name: str) -> FailureCode:
        if not code_name or code_name == "NONE":
            return FailureCode.EXTERNAL_FAILSAFE

        return FailureCode.__members__.get(
            code_name,
            FailureCode.EXTERNAL_FAILSAFE,
        )

    def update(
        self,
        context: MissionContext,
        now_s: float,
    ) -> MissionState:
        if self.state in {MissionState.COMPLETE, MissionState.ABORT}:
            return self.state

        if self.state is not MissionState.IDLE and not context.connected:
            self._abort(
                now_s=now_s,
                reason="비행제어기 연결이 끊어졌습니다.",
                failure_code=FailureCode.CONNECTION_LOST,
            )
            return self.state

        if context.failsafe_triggered:
            failure_code = self._resolve_failsafe_code(context.failsafe_code)
            reason = context.failsafe_reason or "Failsafe 신호가 감지되었습니다."
            self._abort(
                now_s=now_s,
                reason=reason,
                failure_code=failure_code,
            )
            return self.state

        if self._check_timeout(now_s):
            return self.state

        match self.state:
            case MissionState.IDLE:
                if context.connected:
                    self._transition(MissionState.PREFLIGHT, now_s, "비행제어기 연결 완료")

            case MissionState.PREFLIGHT:
                if context.health_ok:
                    self._transition(MissionState.ARMING, now_s, "비행 전 상태 점검 완료")

            case MissionState.ARMING:
                if context.armed:
                    self._transition(MissionState.TAKEOFF, now_s, "기체 Arm 완료")

            case MissionState.TAKEOFF:
                if context.altitude_m >= self.takeoff_altitude_m:
                    self._transition(MissionState.HOVER, now_s, "목표 이륙 고도 도달")

            case MissionState.HOVER:
                if context.hover_stable:
                    self._transition(
                        MissionState.FORWARD_TRANSITION,
                        now_s,
                        "호버 안정성 확인",
                    )

            case MissionState.FORWARD_TRANSITION:
                if context.forward_transition_complete:
                    self._transition(MissionState.CRUISE, now_s, "전진 천이 완료")

            case MissionState.CRUISE:
                if context.target_detected:
                    self._transition(MissionState.TARGET_SEARCH, now_s, "목표물 최초 탐지")

            case MissionState.TARGET_SEARCH:
                if context.search_complete:
                    self._transition(
                        MissionState.BACK_TRANSITION,
                        now_s,
                        "목표 탐색 및 위치 확정",
                    )

            case MissionState.BACK_TRANSITION:
                if context.back_transition_complete:
                    self._transition(MissionState.RETURN_HOME, now_s, "역천이 완료")

            case MissionState.RETURN_HOME:
                if context.returned_home:
                    self._transition(MissionState.LAND, now_s, "복귀 지점 도착")

            case MissionState.LAND:
                if context.landed:
                    self._transition(MissionState.COMPLETE, now_s, "착륙 및 임무 완료")

        return self.state
