import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from src.hybrid_mission_controller import (
    HybridControllerConfig,
    HybridMissionController,
    HybridMode,
)
from src.mission_context import MissionContext
from src.offboard_controller import OffboardController
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


class NeverTransitionsFlightController:
    def __init__(self) -> None:
        self.context = MissionContext(
            connected=True,
            in_air=True,
            mission_started=True,
            vtol_state="FW",
        )
        self.calls: list[str] = []

    async def pause_uploaded_mission(self) -> None:
        self.context.mission_paused = True
        self.calls.append("pause")

    async def transition_to_multicopter(self) -> None:
        self.context.vtol_state = "TRANSITION_TO_MC"
        self.calls.append("transition")

    async def return_to_launch(self) -> None:
        self.calls.append("rtl")


def create_target(timestamp_s: float) -> TargetEstimate:
    return TargetEstimate(
        relative_north_m=10.0,
        relative_east_m=0.0,
        confidence=0.9,
        tracking_stable=True,
        timestamp_s=timestamp_s,
    )


def test_hybrid_config_rejects_nonpositive_timeout() -> None:
    with pytest.raises(ValueError):
        HybridControllerConfig(multicopter_transition_timeout_s=0.0)


def test_waiting_for_multicopter_timeout_recovers_to_rtl() -> None:
    async def run_test() -> None:
        fc = NeverTransitionsFlightController()
        plugin = FakeOffboardPlugin(calls=[])
        offboard = OffboardController(
            offboard_plugin=plugin,
            setpoint_factory=lambda *values: values,
        )
        hybrid = HybridMissionController(
            flight_controller=fc,
            offboard_controller=offboard,
            config=HybridControllerConfig(
                multicopter_transition_timeout_s=1.0,
            ),
        )

        await hybrid.request_target_approach(
            create_target(0.0),
            now_s=0.0,
        )
        result = await hybrid.update(
            create_target(1.1),
            now_s=1.1,
        )

        assert result.changed is True
        assert hybrid.mode is HybridMode.RTL
        assert fc.calls[-1] == "rtl"
        assert ("start", None) not in plugin.calls

    asyncio.run(run_test())
