from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from src.event_logger import write_telemetry_log
from src.hybrid_mission_controller import (
    HybridControllerConfig,
    HybridMissionController,
    HybridMode,
    HybridTransition,
)
from src.mission_context import MissionContext
from src.offboard_controller import (
    OffboardController,
    VelocityNedCommand,
)
from src.target_estimate import TargetEstimate


class HybridSimulationScenario(str, Enum):
    NORMAL = "normal"
    LOW_CONFIDENCE = "low_confidence"
    TRACKING_LOSS = "tracking_loss"
    FAILSAFE_DURING_APPROACH = "failsafe_during_approach"
    TRANSITION_TIMEOUT = "transition_timeout"


@dataclass(slots=True)
class VirtualHybridFlightController:
    """HybridMissionController 통합시험용 최소 가상 비행제어기."""

    scenario: HybridSimulationScenario
    transition_duration_s: float = 1.5
    rtl_duration_s: float = 2.0
    context: MissionContext = field(init=False)
    calls: list[str] = field(init=False, default_factory=list)
    time_s: float = field(init=False, default=0.0)
    _transition_requested_s: float | None = field(init=False, default=None)
    _rtl_requested_s: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.transition_duration_s <= 0.0:
            raise ValueError("가상 역천이 시간은 0보다 커야 합니다.")
        if self.rtl_duration_s <= 0.0:
            raise ValueError("가상 RTL 시간은 0보다 커야 합니다.")

        self.context = MissionContext(
            connected=True,
            health_ok=True,
            armed=True,
            in_air=True,
            altitude_m=15.0,
            battery_remaining_pct=80.0,
            gps_fix="FIX_3D",
            satellites=16,
            flight_mode="MISSION",
            vtol_state="FW",
            mission_uploaded=True,
            mission_started=True,
            mission_paused=False,
        )

    async def pause_uploaded_mission(self) -> None:
        self.calls.append("pause_uploaded_mission")
        self.context.mission_paused = True
        self.context.flight_mode = "HOLD"

    async def transition_to_multicopter(self) -> None:
        self.calls.append("transition_to_multicopter")
        self.context.vtol_state = "TRANSITION_TO_MC"
        self._transition_requested_s = self.time_s

    async def return_to_launch(self) -> None:
        self.calls.append("return_to_launch")
        self.context.flight_mode = "RTL"
        self._rtl_requested_s = self.time_s

    def step(self, dt_s: float) -> None:
        if dt_s <= 0.0:
            raise ValueError("가상 FC 갱신 간격은 0보다 커야 합니다.")

        self.time_s = round(self.time_s + dt_s, 6)

        if (
            self._transition_requested_s is not None
            and self.scenario is not HybridSimulationScenario.TRANSITION_TIMEOUT
            and self.time_s - self._transition_requested_s
            >= self.transition_duration_s
        ):
            self.context.vtol_state = "MC"
            self.context.airspeed_m_s = 0.0

        if (
            self._rtl_requested_s is not None
            and self.time_s - self._rtl_requested_s >= self.rtl_duration_s
        ):
            self.context.returned_home = True


@dataclass(slots=True)
class VirtualOffboardPlugin:
    """MAVSDK Offboard 플러그인의 명령 수신 동작을 모사한다."""

    calls: list[tuple[str, Any]]
    active: bool = False
    last_setpoint: tuple[float, float, float, float] | None = None

    async def set_velocity_ned(self, setpoint: Any) -> None:
        values = tuple(float(value) for value in setpoint)
        if len(values) != 4:
            raise ValueError("가상 Offboard Setpoint는 4개 값이어야 합니다.")
        self.last_setpoint = values  # type: ignore[assignment]
        self.calls.append(("set_velocity_ned", values))

    async def start(self) -> None:
        self.active = True
        self.calls.append(("start", None))

    async def stop(self) -> None:
        self.active = False
        self.calls.append(("stop", None))


def tuple_setpoint_factory(
    north_m_s: float,
    east_m_s: float,
    down_m_s: float,
    yaw_deg: float,
) -> tuple[float, float, float, float]:
    return north_m_s, east_m_s, down_m_s, yaw_deg


@dataclass(slots=True)
class VirtualTargetModel:
    """Offboard 속도 명령에 따라 상대 위치가 감소하는 가상 표적 모델."""

    relative_north_m: float = 18.0
    relative_east_m: float = -6.0
    relative_down_m: float = 0.5
    confidence: float = 0.92
    tracking_stable: bool = True
    source: str = "VIRTUAL_TARGET"

    def __post_init__(self) -> None:
        values = (
            self.relative_north_m,
            self.relative_east_m,
            self.relative_down_m,
            self.confidence,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("가상 표적 값은 유한한 숫자여야 합니다.")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("가상 표적 신뢰도는 0 이상 1 이하여야 합니다.")

    def estimate(self, now_s: float) -> TargetEstimate:
        return TargetEstimate(
            relative_north_m=self.relative_north_m,
            relative_east_m=self.relative_east_m,
            relative_down_m=self.relative_down_m,
            confidence=self.confidence,
            tracking_stable=self.tracking_stable,
            timestamp_s=now_s,
            source=self.source,
        )

    def apply_command(
        self,
        command: VelocityNedCommand,
        dt_s: float,
    ) -> None:
        if dt_s <= 0.0:
            raise ValueError("표적 모델 갱신 간격은 0보다 커야 합니다.")

        self.relative_north_m -= command.north_m_s * dt_s
        self.relative_east_m -= command.east_m_s * dt_s
        self.relative_down_m -= command.down_m_s * dt_s

        if abs(self.relative_north_m) < 1e-9:
            self.relative_north_m = 0.0
        if abs(self.relative_east_m) < 1e-9:
            self.relative_east_m = 0.0
        if abs(self.relative_down_m) < 1e-9:
            self.relative_down_m = 0.0


@dataclass(slots=True)
class HybridSimulationResult:
    scenario: HybridSimulationScenario
    final_mode: HybridMode
    duration_s: float
    returned_home: bool
    target_aligned: bool
    rejected_before_pause: bool
    transitions: list[HybridTransition]
    telemetry_rows: list[dict[str, object]]
    flight_controller_calls: list[str]
    offboard_calls: list[tuple[str, Any]]
    final_target: TargetEstimate

    @property
    def completed_safely(self) -> bool:
        return bool(
            self.final_mode is HybridMode.RTL
            and self.returned_home
        )


def create_hybrid_telemetry_row(
    now_s: float,
    controller: HybridMissionController,
    context: MissionContext,
    target: TargetEstimate,
    command: VelocityNedCommand | None,
    reason: str,
) -> dict[str, object]:
    return {
        "time_s": f"{now_s:.2f}",
        "hybrid_mode": controller.mode.value,
        "reason": reason,
        "connected": context.connected,
        "in_air": context.in_air,
        "flight_mode": context.flight_mode,
        "vtol_state": context.vtol_state,
        "mission_started": context.mission_started,
        "mission_paused": context.mission_paused,
        "failsafe_triggered": context.failsafe_triggered,
        "target_north_m": f"{target.relative_north_m:.3f}",
        "target_east_m": f"{target.relative_east_m:.3f}",
        "target_down_m": f"{target.relative_down_m:.3f}",
        "target_distance_m": f"{target.horizontal_distance_m:.3f}",
        "target_confidence": f"{target.confidence:.3f}",
        "tracking_stable": target.tracking_stable,
        "command_north_m_s": (
            f"{command.north_m_s:.3f}" if command is not None else ""
        ),
        "command_east_m_s": (
            f"{command.east_m_s:.3f}" if command is not None else ""
        ),
        "command_down_m_s": (
            f"{command.down_m_s:.3f}" if command is not None else ""
        ),
        "returned_home": context.returned_home,
    }


async def run_hybrid_simulation_async(
    scenario: HybridSimulationScenario = HybridSimulationScenario.NORMAL,
    dt_s: float = 0.25,
    max_duration_s: float = 30.0,
    aligned_hold_s: float = 0.75,
) -> HybridSimulationResult:
    """MissionRaw→역천이→Offboard 접근→RTL 전체 흐름을 가상 검증한다."""

    if dt_s <= 0.0:
        raise ValueError("시뮬레이션 간격은 0보다 커야 합니다.")
    if max_duration_s <= 0.0:
        raise ValueError("최대 실행시간은 0보다 커야 합니다.")
    if aligned_hold_s < 0.0:
        raise ValueError("정렬 유지시간은 0 이상이어야 합니다.")

    fc = VirtualHybridFlightController(scenario=scenario)
    plugin = VirtualOffboardPlugin(calls=[])
    offboard = OffboardController(
        offboard_plugin=plugin,
        setpoint_factory=tuple_setpoint_factory,
    )
    hybrid = HybridMissionController(
        flight_controller=fc,
        offboard_controller=offboard,
        config=HybridControllerConfig(
            multicopter_transition_timeout_s=3.0,
        ),
    )
    target_model = VirtualTargetModel()

    if scenario is HybridSimulationScenario.LOW_CONFIDENCE:
        target_model.confidence = 0.45

    now_s = 0.0
    aligned_since_s: float | None = None
    offboard_started_s: float | None = None
    telemetry_rows: list[dict[str, object]] = []

    initial_target = target_model.estimate(now_s)
    request_result = await hybrid.request_target_approach(
        target=initial_target,
        now_s=now_s,
    )
    telemetry_rows.append(
        create_hybrid_telemetry_row(
            now_s=now_s,
            controller=hybrid,
            context=fc.context,
            target=initial_target,
            command=request_result.command,
            reason=request_result.reason,
        )
    )

    rejected_before_pause = not request_result.changed
    if rejected_before_pause:
        return HybridSimulationResult(
            scenario=scenario,
            final_mode=hybrid.mode,
            duration_s=now_s,
            returned_home=fc.context.returned_home,
            target_aligned=False,
            rejected_before_pause=True,
            transitions=list(hybrid.history),
            telemetry_rows=telemetry_rows,
            flight_controller_calls=list(fc.calls),
            offboard_calls=list(plugin.calls),
            final_target=initial_target,
        )

    while now_s < max_duration_s:
        now_s = round(now_s + dt_s, 6)
        fc.step(dt_s)

        if hybrid.mode is HybridMode.OFFBOARD_APPROACH:
            if offboard_started_s is None:
                offboard_started_s = now_s

            elapsed_offboard_s = now_s - offboard_started_s
            if (
                scenario is HybridSimulationScenario.TRACKING_LOSS
                and elapsed_offboard_s >= 1.0
            ):
                target_model.tracking_stable = False

            if (
                scenario is HybridSimulationScenario.FAILSAFE_DURING_APPROACH
                and elapsed_offboard_s >= 1.0
            ):
                fc.context.failsafe_triggered = True
                fc.context.failsafe_code = "SIMULATED_FAILSAFE"
                fc.context.failsafe_reason = "가상 Offboard 접근 중 Failsafe"
                fc.context.failsafe_action = "RTL"

        target = target_model.estimate(now_s)
        update_result = await hybrid.update(
            target=target,
            now_s=now_s,
        )

        if update_result.command is not None:
            target_model.apply_command(
                command=update_result.command,
                dt_s=dt_s,
            )

        telemetry_rows.append(
            create_hybrid_telemetry_row(
                now_s=now_s,
                controller=hybrid,
                context=fc.context,
                target=target_model.estimate(now_s),
                command=update_result.command,
                reason=update_result.reason,
            )
        )

        if hybrid.mode is HybridMode.TARGET_ALIGNED:
            if aligned_since_s is None:
                aligned_since_s = now_s
            if now_s - aligned_since_s >= aligned_hold_s:
                finish_result = await hybrid.finish_target_task()
                telemetry_rows.append(
                    create_hybrid_telemetry_row(
                        now_s=now_s,
                        controller=hybrid,
                        context=fc.context,
                        target=target_model.estimate(now_s),
                        command=finish_result.command,
                        reason=finish_result.reason,
                    )
                )

        if hybrid.mode is HybridMode.RTL and fc.context.returned_home:
            break
        if hybrid.mode is HybridMode.ABORT:
            break

    final_target = target_model.estimate(now_s)
    return HybridSimulationResult(
        scenario=scenario,
        final_mode=hybrid.mode,
        duration_s=now_s,
        returned_home=fc.context.returned_home,
        target_aligned=any(
            transition.current_mode is HybridMode.TARGET_ALIGNED
            for transition in hybrid.history
        ),
        rejected_before_pause=False,
        transitions=list(hybrid.history),
        telemetry_rows=telemetry_rows,
        flight_controller_calls=list(fc.calls),
        offboard_calls=list(plugin.calls),
        final_target=final_target,
    )


def save_hybrid_simulation_log(
    result: HybridSimulationResult,
    output_path: str | Path,
) -> Path:
    return write_telemetry_log(
        rows=result.telemetry_rows,
        output_path=output_path,
    )
