from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.command_guard import CommandGuard, GuardCode, GuardResult
from src.offboard_controller import (
    OffboardController,
    OffboardState,
    VelocityNedCommand,
)
from src.target_estimate import TargetEstimate


class HybridMode(str, Enum):
    MISSION_RAW = "MISSION_RAW"
    WAITING_FOR_MULTICOPTER = "WAITING_FOR_MULTICOPTER"
    OFFBOARD_APPROACH = "OFFBOARD_APPROACH"
    TARGET_ALIGNED = "TARGET_ALIGNED"
    RTL = "RTL"
    ABORT = "ABORT"


@dataclass(frozen=True, slots=True)
class HybridControllerConfig:
    """MissionRaw-Offboard 전환 절차의 시간 제한 설정."""

    multicopter_transition_timeout_s: float = 6.0

    def __post_init__(self) -> None:
        if self.multicopter_transition_timeout_s <= 0.0:
            raise ValueError("역천이 제한시간은 0보다 커야 합니다.")


@dataclass(frozen=True, slots=True)
class HybridTransition:
    previous_mode: HybridMode
    current_mode: HybridMode
    reason: str


@dataclass(frozen=True, slots=True)
class HybridUpdateResult:
    mode: HybridMode
    changed: bool
    reason: str
    command: VelocityNedCommand | None = None
    guard_result: GuardResult | None = None


class HybridMissionController:
    """MissionRaw와 Offboard 접근을 안전하게 전환하는 상위 제어기."""

    def __init__(
        self,
        flight_controller: Any,
        offboard_controller: OffboardController,
        command_guard: CommandGuard | None = None,
        config: HybridControllerConfig | None = None,
    ) -> None:
        required_methods = (
            "pause_uploaded_mission",
            "transition_to_multicopter",
            "return_to_launch",
        )
        missing = [
            method
            for method in required_methods
            if not callable(getattr(flight_controller, method, None))
        ]
        if missing:
            raise TypeError(
                "비행제어기에 필요한 메서드가 없습니다: "
                + ", ".join(missing)
            )

        if getattr(flight_controller, "context", None) is None:
            raise TypeError("비행제어기에 MissionContext가 필요합니다.")

        self.flight_controller = flight_controller
        self.offboard_controller = offboard_controller
        self.command_guard = command_guard or CommandGuard()
        self.config = config or HybridControllerConfig()
        self.mode = HybridMode.MISSION_RAW
        self.history: list[HybridTransition] = []
        self.last_reason = "MissionRaw 임무 제어 중"
        self._waiting_started_s: float | None = None

    def _transition(
        self,
        new_mode: HybridMode,
        reason: str,
    ) -> None:
        previous_mode = self.mode
        self.mode = new_mode
        self.last_reason = reason
        self.history.append(
            HybridTransition(
                previous_mode=previous_mode,
                current_mode=new_mode,
                reason=reason,
            )
        )

    def _result(
        self,
        *,
        changed: bool,
        reason: str,
        command: VelocityNedCommand | None = None,
        guard_result: GuardResult | None = None,
    ) -> HybridUpdateResult:
        return HybridUpdateResult(
            mode=self.mode,
            changed=changed,
            reason=reason,
            command=command,
            guard_result=guard_result,
        )

    async def request_target_approach(
        self,
        target: TargetEstimate,
        now_s: float,
    ) -> HybridUpdateResult:
        if self.mode is not HybridMode.MISSION_RAW:
            raise RuntimeError(
                "MissionRaw 모드에서만 표적 접근을 요청할 수 있습니다."
            )

        context = self.flight_controller.context

        vehicle_result = self.command_guard.evaluate_vehicle(
            context,
            require_mission_running=True,
            require_mission_paused=False,
            require_multicopter=False,
        )
        if not vehicle_result.allowed:
            return self._result(
                changed=False,
                reason=vehicle_result.reason,
                guard_result=vehicle_result,
            )

        target_result = self.command_guard.evaluate_target(
            target,
            now_s,
        )
        if not target_result.allowed:
            return self._result(
                changed=False,
                reason=target_result.reason,
                guard_result=target_result,
            )

        await self.flight_controller.pause_uploaded_mission()

        if self.flight_controller.context.vtol_state != "MC":
            await self.flight_controller.transition_to_multicopter()
            self._waiting_started_s = now_s
            self._transition(
                HybridMode.WAITING_FOR_MULTICOPTER,
                "MissionRaw 일시정지 후 멀티콥터 역천이 요청",
            )
            return self._result(
                changed=True,
                reason=self.last_reason,
            )

        return await self._activate_offboard(target, now_s)

    async def _activate_offboard(
        self,
        target: TargetEstimate,
        now_s: float,
    ) -> HybridUpdateResult:
        guard_result = self.command_guard.evaluate_offboard_entry(
            self.flight_controller.context,
            target,
            now_s,
        )
        if not guard_result.allowed:
            return await self._recover_to_rtl(guard_result.reason)

        await self.offboard_controller.prime(
            yaw_deg=target.bearing_deg
        )
        await self.offboard_controller.start()
        self._waiting_started_s = None
        self._transition(
            HybridMode.OFFBOARD_APPROACH,
            "초기 Setpoint 전송 후 Offboard 접근 시작",
        )
        return self._result(
            changed=True,
            reason=self.last_reason,
            guard_result=guard_result,
        )

    async def update(
        self,
        target: TargetEstimate,
        now_s: float,
    ) -> HybridUpdateResult:
        if self.mode is HybridMode.WAITING_FOR_MULTICOPTER:
            context = self.flight_controller.context

            if context.failsafe_triggered or not context.connected:
                return await self._recover_to_rtl(
                    "역천이 대기 중 안전 조건이 해제되었습니다."
                )

            target_result = self.command_guard.evaluate_target(
                target,
                now_s,
            )
            if not target_result.allowed:
                return await self._recover_to_rtl(
                    target_result.reason
                )

            if (
                self._waiting_started_s is not None
                and now_s - self._waiting_started_s
                > self.config.multicopter_transition_timeout_s
            ):
                return await self._recover_to_rtl(
                    "멀티콥터 역천이 제한시간을 초과했습니다."
                )

            if not context.mission_paused:
                return self._result(
                    changed=False,
                    reason="MissionRaw 일시정지 확인 대기",
                )

            if context.vtol_state != "MC":
                return self._result(
                    changed=False,
                    reason="멀티콥터 역천이 완료 대기",
                )

            return await self._activate_offboard(target, now_s)

        if self.mode is HybridMode.OFFBOARD_APPROACH:
            guard_result = self.command_guard.evaluate_offboard_entry(
                self.flight_controller.context,
                target,
                now_s,
            )
            if not guard_result.allowed:
                return await self._recover_to_rtl(
                    guard_result.reason
                )

            if self.offboard_controller.is_target_aligned(target):
                command = await self.offboard_controller.hold()
                self._transition(
                    HybridMode.TARGET_ALIGNED,
                    "표적 접근 허용오차 진입 및 정렬 완료",
                )
                return self._result(
                    changed=True,
                    reason=self.last_reason,
                    command=command,
                    guard_result=guard_result,
                )

            command = (
                await self.offboard_controller.send_target_command(
                    target
                )
            )
            return self._result(
                changed=False,
                reason="표적 상대 위치 기반 Offboard 접근 중",
                command=command,
                guard_result=guard_result,
            )

        if self.mode is HybridMode.TARGET_ALIGNED:
            command = await self.offboard_controller.hold()
            return self._result(
                changed=False,
                reason="표적 정렬 위치 유지",
                command=command,
            )

        return self._result(
            changed=False,
            reason=self.last_reason,
        )

    async def finish_target_task(self) -> HybridUpdateResult:
        if self.mode not in {
            HybridMode.OFFBOARD_APPROACH,
            HybridMode.TARGET_ALIGNED,
        }:
            raise RuntimeError(
                "Offboard 접근 또는 정렬 상태에서만 임무를 종료할 수 있습니다."
            )

        if self.offboard_controller.state is OffboardState.ACTIVE:
            await self.offboard_controller.hold()
        await self.offboard_controller.stop()
        await self.flight_controller.return_to_launch()
        self._transition(
            HybridMode.RTL,
            "표적 임무 완료 후 Offboard 종료 및 RTL 전환",
        )
        return self._result(
            changed=True,
            reason=self.last_reason,
        )

    async def _recover_to_rtl(
        self,
        reason: str,
    ) -> HybridUpdateResult:
        try:
            if self.offboard_controller.state is OffboardState.ACTIVE:
                await self.offboard_controller.hold()
            await self.offboard_controller.stop()
            await self.flight_controller.return_to_launch()
        except Exception as error:
            abort_reason = (
                f"{reason} RTL 복구 실패: "
                f"{type(error).__name__}: {error}"
            )
            self._transition(HybridMode.ABORT, abort_reason)
            return self._result(
                changed=True,
                reason=abort_reason,
                guard_result=GuardResult(
                    allowed=False,
                    code=GuardCode.FAILSAFE_ACTIVE,
                    reason=reason,
                ),
            )

        self._waiting_started_s = None
        rtl_reason = f"{reason} Offboard 중단 후 RTL 전환"
        self._transition(HybridMode.RTL, rtl_reason)
        return self._result(
            changed=True,
            reason=rtl_reason,
        )
