import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

from src.offboard_controller import (
    OffboardConfig,
    OffboardController,
    OffboardState,
)
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


def setpoint_factory(
    north_m_s: float,
    east_m_s: float,
    down_m_s: float,
    yaw_deg: float,
) -> tuple[float, float, float, float]:
    return north_m_s, east_m_s, down_m_s, yaw_deg


def create_target(
    north: float = 10.0,
    east: float = 0.0,
    down: float = 0.0,
) -> TargetEstimate:
    return TargetEstimate(
        relative_north_m=north,
        relative_east_m=east,
        relative_down_m=down,
        confidence=0.9,
        tracking_stable=True,
        timestamp_s=0.0,
    )


def create_controller() -> tuple[FakeOffboardPlugin, OffboardController]:
    plugin = FakeOffboardPlugin(calls=[])
    return plugin, OffboardController(
        offboard_plugin=plugin,
        setpoint_factory=setpoint_factory,
    )


def test_offboard_config_rejects_nonpositive_speed() -> None:
    with pytest.raises(ValueError):
        OffboardConfig(maximum_horizontal_speed_m_s=0.0)


def test_offboard_requires_plugin_methods() -> None:
    with pytest.raises(TypeError):
        OffboardController(
            offboard_plugin=object(),
            setpoint_factory=setpoint_factory,
        )


def test_compute_approach_command_uses_proportional_gain() -> None:
    _, controller = create_controller()
    command = controller.compute_approach_command(
        create_target(north=4.0, east=2.0, down=1.0)
    )
    assert command.north_m_s == pytest.approx(1.4)
    assert command.east_m_s == pytest.approx(0.7)
    assert command.down_m_s == pytest.approx(0.3)


def test_compute_approach_command_limits_horizontal_speed() -> None:
    _, controller = create_controller()
    command = controller.compute_approach_command(
        create_target(north=100.0, east=100.0)
    )
    assert command.horizontal_speed_m_s == pytest.approx(4.0)


def test_prime_sends_zero_setpoint() -> None:
    async def run_test() -> None:
        plugin, controller = create_controller()
        await controller.prime(yaw_deg=90.0)
        assert controller.state is OffboardState.PRIMED
        assert plugin.calls == [
            ("set_velocity_ned", (0.0, 0.0, 0.0, 90.0))
        ]

    asyncio.run(run_test())


def test_start_requires_prime() -> None:
    async def run_test() -> None:
        _, controller = create_controller()
        with pytest.raises(RuntimeError):
            await controller.start()

    asyncio.run(run_test())


def test_start_and_send_target_command() -> None:
    async def run_test() -> None:
        plugin, controller = create_controller()
        await controller.prime()
        await controller.start()
        command = await controller.send_target_command(
            create_target(north=2.0, east=0.0)
        )
        assert controller.state is OffboardState.ACTIVE
        assert command.north_m_s == pytest.approx(0.7)
        assert ("start", None) in plugin.calls
        assert plugin.calls[-1][0] == "set_velocity_ned"

    asyncio.run(run_test())


def test_alignment_and_stop_are_safe() -> None:
    async def run_test() -> None:
        plugin, controller = create_controller()
        assert controller.is_target_aligned(
            create_target(north=0.5, east=0.5, down=0.5)
        ) is True
        await controller.prime()
        await controller.start()
        await controller.stop()
        assert controller.state is OffboardState.STOPPED
        assert plugin.calls[-1] == ("stop", None)

    asyncio.run(run_test())
