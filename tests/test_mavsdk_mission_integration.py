from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from src.mavsdk_fc import MavsdkFlightController
from src.mission_manager import create_flight_controller, create_telemetry_row
from src.mission_plan import MissionPlan, Waypoint
from src.state_machine import MissionState, MissionStateMachine


async def one_value(value: Any):
    yield value


def create_plan() -> MissionPlan:
    return MissionPlan(
        name="integration_mission",
        waypoints=(
            Waypoint(
                name="HOME",
                latitude_deg=36.3210,
                longitude_deg=127.4080,
                relative_altitude_m=10.0,
                acceptance_radius_m=5.0,
                fly_through=False,
            ),
            Waypoint(
                name="WPT1",
                latitude_deg=36.3212,
                longitude_deg=127.4082,
                relative_altitude_m=20.0,
                acceptance_radius_m=8.0,
            ),
        ),
    )


@dataclass
class FakeMissionRaw:
    calls: list[tuple[str, Any]]
    progress_values: list[tuple[int, int]]

    async def upload_mission(self, mission_items: list[Any]) -> None:
        self.calls.append(("upload_mission", mission_items))

    async def start_mission(self) -> None:
        self.calls.append(("start_mission", None))

    async def pause_mission(self) -> None:
        self.calls.append(("pause_mission", None))

    async def clear_mission(self) -> None:
        self.calls.append(("clear_mission", None))

    async def mission_progress(self):
        for current, total in self.progress_values:
            yield SimpleNamespace(current=current, total=total)


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
        return one_value(False)

    def position(self):
        return one_value(
            SimpleNamespace(
                latitude_deg=36.321,
                longitude_deg=127.408,
                relative_altitude_m=0.0,
            )
        )

    def fixedwing_metrics(self):
        return one_value(SimpleNamespace(airspeed_m_s=0.0))

    def vtol_state(self):
        return one_value(SimpleNamespace(name="MC"))

    def in_air(self):
        return one_value(False)

    def battery(self):
        return one_value(SimpleNamespace(remaining_percent=1.0))

    def gps_info(self):
        return one_value(
            SimpleNamespace(
                num_satellites=15,
                fix_type=SimpleNamespace(name="FIX_3D"),
            )
        )

    def flight_mode(self):
        return one_value(SimpleNamespace(name="HOLD"))


class FakeAction:
    pass


class FakeSystem:
    def __init__(
        self,
        progress_values: list[tuple[int, int]] | None = None,
    ) -> None:
        self.connected_address: str | None = None
        self.core = FakeCore()
        self.telemetry = FakeTelemetry()
        self.action = FakeAction()
        self.mission_raw = FakeMissionRaw(
            calls=[],
            progress_values=progress_values or [],
        )

    async def connect(self, system_address: str) -> None:
        self.connected_address = system_address


def fake_item_factory(*args: Any) -> tuple[Any, ...]:
    return args


def test_connect_initializes_mission_uploader() -> None:
    async def run_test() -> None:
        controller = MavsdkFlightController(
            system=FakeSystem(),
            mission_item_factory=fake_item_factory,
        )

        assert controller.mission_uploader is None
        await controller.connect()
        assert controller.mission_uploader is not None
        await controller.close()

    asyncio.run(run_test())


def test_upload_configured_mission_updates_context() -> None:
    async def run_test() -> None:
        system = FakeSystem()
        controller = MavsdkFlightController(
            system=system,
            mission_plan=create_plan(),
            mission_item_factory=fake_item_factory,
        )

        result = await controller.upload_mission()

        assert result.mission_name == "integration_mission"
        assert result.uploaded_items == 2
        assert system.mission_raw.calls[0] == ("clear_mission", None)
        assert system.mission_raw.calls[1][0] == "upload_mission"
        assert len(system.mission_raw.calls[1][1]) == 2
        assert controller.context.mission_uploaded is True
        assert controller.context.raw_mission_total == 2

    asyncio.run(run_test())


def test_upload_requires_mission_plan() -> None:
    async def run_test() -> None:
        controller = MavsdkFlightController(
            system=FakeSystem(),
            mission_item_factory=fake_item_factory,
        )

        with pytest.raises(RuntimeError):
            await controller.upload_mission()

    asyncio.run(run_test())


def test_start_requires_uploaded_mission() -> None:
    async def run_test() -> None:
        controller = MavsdkFlightController(
            system=FakeSystem(),
            mission_plan=create_plan(),
            mission_item_factory=fake_item_factory,
        )

        with pytest.raises(RuntimeError):
            await controller.start_uploaded_mission()

    asyncio.run(run_test())


def test_start_uploaded_mission_updates_context() -> None:
    async def run_test() -> None:
        system = FakeSystem()
        controller = MavsdkFlightController(
            system=system,
            mission_plan=create_plan(),
            mission_item_factory=fake_item_factory,
        )

        await controller.upload_mission()
        await controller.start_uploaded_mission()

        assert ("start_mission", None) in system.mission_raw.calls
        assert controller.context.mission_started is True
        assert controller.context.mission_paused is False

    asyncio.run(run_test())


def test_pause_uploaded_mission_updates_context() -> None:
    async def run_test() -> None:
        system = FakeSystem()
        controller = MavsdkFlightController(
            system=system,
            mission_plan=create_plan(),
            mission_item_factory=fake_item_factory,
        )

        await controller.upload_mission()
        await controller.start_uploaded_mission()
        await controller.pause_uploaded_mission()

        assert ("pause_mission", None) in system.mission_raw.calls
        assert controller.context.mission_paused is True

    asyncio.run(run_test())


def test_clear_uploaded_mission_resets_context() -> None:
    async def run_test() -> None:
        system = FakeSystem()
        controller = MavsdkFlightController(
            system=system,
            mission_plan=create_plan(),
            mission_item_factory=fake_item_factory,
        )

        await controller.upload_mission()
        await controller.start_uploaded_mission()
        await controller.clear_uploaded_mission()

        assert system.mission_raw.calls[-1] == ("clear_mission", None)
        assert controller.context.mission_uploaded is False
        assert controller.context.mission_started is False
        assert controller.context.raw_mission_total == 0

    asyncio.run(run_test())


def test_mission_progress_stream_updates_context() -> None:
    async def run_test() -> None:
        system = FakeSystem(
            progress_values=[
                (0, 2),
                (1, 2),
                (2, 2),
            ]
        )
        controller = MavsdkFlightController(
            system=system,
            mission_plan=create_plan(),
            mission_item_factory=fake_item_factory,
        )

        await controller.upload_mission()
        await controller.start_uploaded_mission()

        received = [
            progress
            async for progress in controller.mission_progress_stream()
        ]

        assert [progress.progress_pct for progress in received] == [
            0.0,
            50.0,
            100.0,
        ]
        assert controller.context.raw_mission_current == 2
        assert controller.context.raw_mission_total == 2
        assert controller.context.raw_mission_finished is True
        assert controller.context.mission_started is False

    asyncio.run(run_test())


def test_backend_factory_passes_plan_to_mavsdk_controller() -> None:
    plan = create_plan()
    controller = create_flight_controller(
        backend="mavsdk",
        mission_plan=plan,
    )

    assert isinstance(controller, MavsdkFlightController)
    assert controller.mission_plan is plan


def test_telemetry_row_contains_raw_mission_status() -> None:
    controller = MavsdkFlightController(
        system=FakeSystem(),
        mission_plan=create_plan(),
        mission_item_factory=fake_item_factory,
    )
    controller.context.mission_uploaded = True
    controller.context.mission_started = True
    controller.context.raw_mission_current = 1
    controller.context.raw_mission_total = 2
    controller.context.raw_mission_progress_pct = 50.0

    machine = MissionStateMachine()
    row = create_telemetry_row(
        now_s=1.0,
        state=MissionState.IDLE,
        context=controller.context,
        machine=machine,
    )

    assert row["mission_uploaded"] is True
    assert row["mission_started"] is True
    assert row["raw_mission_current"] == 1
    assert row["raw_mission_total"] == 2
    assert row["raw_mission_progress_pct"] == "50.00"
