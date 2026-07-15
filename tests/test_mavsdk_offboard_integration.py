from dataclasses import dataclass
from typing import Any

import pytest

from src.mavsdk_fc import MavsdkFlightController
from src.offboard_controller import OffboardController


@dataclass
class FakeOffboard:
    calls: list[tuple[str, Any]]

    async def set_velocity_ned(self, setpoint: Any) -> None:
        self.calls.append(("set_velocity_ned", setpoint))

    async def start(self) -> None:
        self.calls.append(("start", None))

    async def stop(self) -> None:
        self.calls.append(("stop", None))


class FakeSystem:
    def __init__(self, include_offboard: bool = True) -> None:
        if include_offboard:
            self.offboard = FakeOffboard(calls=[])


def test_mavsdk_fc_creates_offboard_controller_without_starting() -> None:
    system = FakeSystem()
    controller = MavsdkFlightController(
        system=system,
        offboard_setpoint_factory=lambda *args: args,
    )

    offboard = controller.create_offboard_controller()

    assert isinstance(offboard, OffboardController)
    assert controller.offboard_controller is offboard
    assert system.offboard.calls == []


def test_mavsdk_fc_rejects_missing_offboard_plugin() -> None:
    controller = MavsdkFlightController(
        system=FakeSystem(include_offboard=False),
    )

    with pytest.raises(RuntimeError):
        controller.create_offboard_controller()
