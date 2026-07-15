from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from src.flight_controller import FlightControllerInterface
from src.mavsdk_fc import MavsdkFlightController
from src.state_machine import MissionState


async def one_value(value: Any):
    yield value


@dataclass
class FakeAction:
    calls: list[tuple[str, Any]]

    async def arm(self) -> None:
        self.calls.append(("arm", None))

    async def set_takeoff_altitude(self, altitude_m: float) -> None:
        self.calls.append(("set_takeoff_altitude", altitude_m))

    async def takeoff(self) -> None:
        self.calls.append(("takeoff", None))

    async def transition_to_fixedwing(self) -> None:
        self.calls.append(("transition_to_fixedwing", None))

    async def transition_to_multicopter(self) -> None:
        self.calls.append(("transition_to_multicopter", None))

    async def return_to_launch(self) -> None:
        self.calls.append(("return_to_launch", None))

    async def land(self) -> None:
        self.calls.append(("land", None))


class FakeCore:
    def connection_state(self):
        return one_value(SimpleNamespace(is_connected=True))


class FakeTelemetry:
    def health(self):
        return one_value(
            SimpleNamespace(
                is_armable=True,
                is_global_position_ok=True,
                is_home_position_ok=True,
            )
        )

    def armed(self):
        return one_value(True)

    def position(self):
        return one_value(
            SimpleNamespace(
                latitude_deg=36.321,
                longitude_deg=127.408,
                relative_altitude_m=12.5,
            )
        )

    def fixedwing_metrics(self):
        return one_value(SimpleNamespace(airspeed_m_s=18.2))

    def vtol_state(self):
        return one_value(SimpleNamespace(name="FW"))

    def in_air(self):
        return one_value(True)

    def battery(self):
        return one_value(SimpleNamespace(remaining_percent=0.76))

    def gps_info(self):
        return one_value(
            SimpleNamespace(
                num_satellites=16,
                fix_type=SimpleNamespace(name="RTK_FIXED"),
            )
        )

    def flight_mode(self):
        return one_value(SimpleNamespace(name="MISSION"))


class FakeSystem:
    def __init__(self) -> None:
        self.connected_address: str | None = None
        self.core = FakeCore()
        self.telemetry = FakeTelemetry()
        self.action = FakeAction(calls=[])

    async def connect(self, system_address: str) -> None:
        self.connected_address = system_address


def test_mavsdk_fc_implements_interface() -> None:
    controller = MavsdkFlightController(system=FakeSystem())
    assert isinstance(controller, FlightControllerInterface)


def test_mavsdk_fc_connects() -> None:
    async def run_test() -> None:
        system = FakeSystem()
        controller = MavsdkFlightController(
            connection_url="udpin://0.0.0.0:14540",
            system=system,
        )
        await controller.connect()
        assert controller.context.connected is True
        assert system.connected_address == "udpin://0.0.0.0:14540"
        await controller.close()
    asyncio.run(run_test())


def test_mavsdk_fc_arm_command() -> None:
    async def run_test() -> None:
        system = FakeSystem()
        controller = MavsdkFlightController(system=system)
        await controller.arm()
        assert ("arm", None) in system.action.calls
    asyncio.run(run_test())


def test_mavsdk_fc_takeoff_commands() -> None:
    async def run_test() -> None:
        system = FakeSystem()
        controller = MavsdkFlightController(system=system)
        await controller.takeoff(15.0)
        assert ("set_takeoff_altitude", 15.0) in system.action.calls
        assert ("takeoff", None) in system.action.calls
    asyncio.run(run_test())


def test_mavsdk_fc_vtol_and_landing_commands() -> None:
    async def run_test() -> None:
        system = FakeSystem()
        controller = MavsdkFlightController(system=system)
        await controller.transition_to_fixed_wing()
        await controller.transition_to_multicopter()
        await controller.return_to_launch()
        await controller.land()
        assert ("transition_to_fixedwing", None) in system.action.calls
        assert ("transition_to_multicopter", None) in system.action.calls
        assert ("return_to_launch", None) in system.action.calls
        assert ("land", None) in system.action.calls
    asyncio.run(run_test())


def test_mavsdk_fc_receives_telemetry() -> None:
    async def run_test() -> None:
        controller = MavsdkFlightController(system=FakeSystem())
        await controller.connect()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        context = await controller.update(
            state=MissionState.FORWARD_TRANSITION,
            dt_s=0.25,
            state_elapsed_s=2.0,
        )
        assert context.health_ok is True
        assert context.armed is True
        assert context.in_air is True
        assert context.altitude_m == 12.5
        assert context.airspeed_m_s == 18.2
        assert context.latitude_deg == 36.321
        assert context.longitude_deg == 127.408
        assert context.battery_remaining_pct == 76.0
        assert context.satellites == 16
        assert context.gps_fix == "RTK_FIXED"
        assert context.flight_mode == "MISSION"
        assert context.vtol_state == "FW"
        assert context.forward_transition_complete is True
        await controller.close()
    asyncio.run(run_test())
