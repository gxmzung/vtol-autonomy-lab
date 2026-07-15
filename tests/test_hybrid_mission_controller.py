import asyncio
from dataclasses import dataclass
from typing import Any

from src.hybrid_mission_controller import (
    HybridMissionController,
    HybridMode,
)
from src.mission_context import MissionContext
from src.offboard_controller import OffboardController, OffboardState
from src.target_estimate import TargetEstimate


@dataclass
class FakeOffboardPlugin:
    calls: list[tuple[str, Any]]

    async def set_velocity_ned(self, setpoint: Any) -> None:
        self.calls.append(("set_velocity_ned", setpoint))

    async def start(self) -> None:
        self.calls.append(("start", None))

    async def stop(self) -> None:
        self.calls.append(("stop", None))


class FakeFlightController:
    def __init__(self, vtol_state: str = "FW") -> None:
        self.context = MissionContext(
            connected=True,
            in_air=True,
            mission_started=True,
            mission_paused=False,
            vtol_state=vtol_state,
        )
        self.calls: list[str] = []

    async def pause_uploaded_mission(self) -> None:
        self.calls.append("pause")
        self.context.mission_paused = True

    async def transition_to_multicopter(self) -> None:
        self.calls.append("transition_mc")

    async def return_to_launch(self) -> None:
        self.calls.append("rtl")


def setpoint_factory(*args: float) -> tuple[float, ...]:
    return args


def create_target(
    north: float = 10.0,
    east: float = 0.0,
    confidence: float = 0.9,
) -> TargetEstimate:
    return TargetEstimate(
        relative_north_m=north,
        relative_east_m=east,
        confidence=confidence,
        tracking_stable=True,
        timestamp_s=10.0,
    )


def create_hybrid(
    vtol_state: str = "FW",
) -> tuple[
    FakeFlightController,
    FakeOffboardPlugin,
    HybridMissionController,
]:
    fc = FakeFlightController(vtol_state=vtol_state)
    plugin = FakeOffboardPlugin(calls=[])
    offboard = OffboardController(
        offboard_plugin=plugin,
        setpoint_factory=setpoint_factory,
    )
    return fc, plugin, HybridMissionController(fc, offboard)


def test_low_confidence_keeps_mission_raw() -> None:
    async def run_test() -> None:
        fc, _, hybrid = create_hybrid()
        result = await hybrid.request_target_approach(
            create_target(confidence=0.4),
            now_s=10.2,
        )
        assert result.changed is False
        assert hybrid.mode is HybridMode.MISSION_RAW
        assert fc.calls == []

    asyncio.run(run_test())


def test_request_pauses_mission_and_requests_back_transition() -> None:
    async def run_test() -> None:
        fc, _, hybrid = create_hybrid(vtol_state="FW")
        result = await hybrid.request_target_approach(
            create_target(),
            now_s=10.2,
        )
        assert result.changed is True
        assert hybrid.mode is HybridMode.WAITING_FOR_MULTICOPTER
        assert fc.calls == ["pause", "transition_mc"]

    asyncio.run(run_test())


def test_waiting_mode_does_not_start_before_mc_confirmation() -> None:
    async def run_test() -> None:
        _, plugin, hybrid = create_hybrid(vtol_state="FW")
        await hybrid.request_target_approach(
            create_target(),
            now_s=10.2,
        )
        result = await hybrid.update(
            create_target(),
            now_s=10.3,
        )
        assert result.changed is False
        assert hybrid.mode is HybridMode.WAITING_FOR_MULTICOPTER
        assert ("start", None) not in plugin.calls

    asyncio.run(run_test())


def test_mc_confirmation_activates_offboard() -> None:
    async def run_test() -> None:
        fc, plugin, hybrid = create_hybrid(vtol_state="FW")
        await hybrid.request_target_approach(
            create_target(),
            now_s=10.2,
        )
        fc.context.vtol_state = "MC"
        result = await hybrid.update(
            create_target(),
            now_s=10.3,
        )
        assert result.changed is True
        assert hybrid.mode is HybridMode.OFFBOARD_APPROACH
        assert hybrid.offboard_controller.state is OffboardState.ACTIVE
        assert ("start", None) in plugin.calls

    asyncio.run(run_test())


def test_offboard_approach_sends_velocity_command() -> None:
    async def run_test() -> None:
        _, plugin, hybrid = create_hybrid(vtol_state="MC")
        await hybrid.request_target_approach(
            create_target(),
            now_s=10.2,
        )
        result = await hybrid.update(
            create_target(north=5.0, east=2.0),
            now_s=10.3,
        )
        assert result.command is not None
        assert result.command.north_m_s > 0.0
        assert plugin.calls[-1][0] == "set_velocity_ned"

    asyncio.run(run_test())


def test_target_alignment_changes_mode() -> None:
    async def run_test() -> None:
        _, _, hybrid = create_hybrid(vtol_state="MC")
        await hybrid.request_target_approach(
            create_target(),
            now_s=10.2,
        )
        result = await hybrid.update(
            create_target(north=0.4, east=0.3),
            now_s=10.3,
        )
        assert result.changed is True
        assert hybrid.mode is HybridMode.TARGET_ALIGNED
        assert result.command is not None
        assert result.command.horizontal_speed_m_s == 0.0

    asyncio.run(run_test())


def test_finish_target_task_stops_offboard_and_requests_rtl() -> None:
    async def run_test() -> None:
        fc, plugin, hybrid = create_hybrid(vtol_state="MC")
        await hybrid.request_target_approach(
            create_target(),
            now_s=10.2,
        )
        await hybrid.update(
            create_target(north=0.4, east=0.3),
            now_s=10.3,
        )
        result = await hybrid.finish_target_task()
        assert result.changed is True
        assert hybrid.mode is HybridMode.RTL
        assert ("stop", None) in plugin.calls
        assert fc.calls[-1] == "rtl"

    asyncio.run(run_test())
