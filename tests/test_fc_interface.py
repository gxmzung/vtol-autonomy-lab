import asyncio

import pytest

from src.flight_controller import FlightControllerInterface
from src.state_machine import MissionState
from src.virtual_fc import SimulationScenario, VirtualFlightController


def test_virtual_fc_implements_interface() -> None:
    flight_controller = VirtualFlightController(scenario=SimulationScenario.NORMAL)
    assert isinstance(flight_controller, FlightControllerInterface)


def test_virtual_fc_connects() -> None:
    async def run_test() -> None:
        flight_controller = VirtualFlightController(scenario=SimulationScenario.NORMAL)
        await flight_controller.connect()
        assert flight_controller.context.connected is True
    asyncio.run(run_test())


def test_arm_requires_health_check() -> None:
    async def run_test() -> None:
        flight_controller = VirtualFlightController(scenario=SimulationScenario.NORMAL)
        await flight_controller.connect()
        with pytest.raises(RuntimeError):
            await flight_controller.arm()
    asyncio.run(run_test())


def test_takeoff_requires_armed_vehicle() -> None:
    async def run_test() -> None:
        flight_controller = VirtualFlightController(scenario=SimulationScenario.NORMAL)
        await flight_controller.connect()
        with pytest.raises(RuntimeError):
            await flight_controller.takeoff(10.0)
    asyncio.run(run_test())


def test_virtual_fc_preflight_health_update() -> None:
    async def run_test() -> None:
        flight_controller = VirtualFlightController(scenario=SimulationScenario.NORMAL)
        await flight_controller.connect()
        context = await flight_controller.update(
            state=MissionState.PREFLIGHT,
            dt_s=0.25,
            state_elapsed_s=1.0,
        )
        assert context.health_ok is True
    asyncio.run(run_test())
