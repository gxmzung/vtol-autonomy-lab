from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from src.fc_validator import (
    FCSafeValidator,
    SafetyInterlockError,
    write_validation_report,
)
from src.mission_context import MissionContext
from src.mission_plan import MissionPlan, Waypoint
from src.mission_raw_builder import build_raw_mission_items


def create_plan() -> MissionPlan:
    return MissionPlan(
        name="safe_validation_test",
        waypoints=(
            Waypoint("HOME", 36.321, 127.408, 10.0, fly_through=False),
            Waypoint("WPT1", 36.322, 127.409, 20.0),
        ),
    )


def downloaded_items():
    return [
        SimpleNamespace(**asdict(item))
        for item in build_raw_mission_items(create_plan())
    ]


async def no_sleep(_: float) -> None:
    return None


class FakeController:
    def __init__(
        self,
        *,
        armed: bool = False,
        in_air: bool = False,
    ) -> None:
        self.connection_url = "serial://COM5:57600"
        self.context = MissionContext(
            connected=False,
            armed=armed,
            in_air=in_air,
            health_ok=True,
            gps_fix="FIX_3D",
            satellites=15,
            battery_remaining_pct=88.0,
            latitude_deg=36.321,
            longitude_deg=127.408,
            altitude_m=0.0,
            flight_mode="HOLD",
            vtol_state="MC",
        )
        self.calls: list[str] = []
        self.closed = False

    async def connect(self) -> None:
        self.calls.append("connect")
        self.context.connected = True

    async def get_vehicle_identification(self):
        self.calls.append("get_vehicle_identification")
        return {"hardware_uid": "ABC123", "legacy_uid": 9876}

    async def upload_mission(self, **kwargs):
        self.calls.append("upload_mission")
        return SimpleNamespace(uploaded_items=2)

    async def download_mission_items(self):
        self.calls.append("download_mission_items")
        return downloaded_items()

    async def close(self) -> None:
        self.calls.append("close")
        self.closed = True


def test_download_only_validation_does_not_upload() -> None:
    async def run_test() -> None:
        controller = FakeController()
        validator = FCSafeValidator(
            controller=controller,
            settle_time_s=0.0,
            sleep_function=no_sleep,
        )

        report = await validator.run(
            mission_plan=create_plan(),
            upload=False,
            verify_download=True,
        )

        assert report.verification_passed is True
        assert report.upload_performed is False
        assert "upload_mission" not in controller.calls
        assert controller.closed is True

    asyncio.run(run_test())


def test_upload_then_download_validation() -> None:
    async def run_test() -> None:
        controller = FakeController()
        validator = FCSafeValidator(
            controller=controller,
            settle_time_s=0.0,
            sleep_function=no_sleep,
        )

        report = await validator.run(
            mission_plan=create_plan(),
            upload=True,
            verify_download=True,
        )

        assert report.upload_performed is True
        assert report.download_performed is True
        assert report.verification_passed is True
        assert controller.calls.index("upload_mission") < controller.calls.index(
            "download_mission_items"
        )

    asyncio.run(run_test())


def test_armed_vehicle_triggers_interlock() -> None:
    async def run_test() -> None:
        controller = FakeController(armed=True)
        validator = FCSafeValidator(
            controller=controller,
            settle_time_s=0.0,
            sleep_function=no_sleep,
        )

        with pytest.raises(SafetyInterlockError):
            await validator.run(
                mission_plan=create_plan(),
                upload=True,
            )

        assert "upload_mission" not in controller.calls
        assert controller.closed is True

    asyncio.run(run_test())


def test_in_air_vehicle_triggers_interlock() -> None:
    async def run_test() -> None:
        controller = FakeController(in_air=True)
        validator = FCSafeValidator(
            controller=controller,
            settle_time_s=0.0,
            sleep_function=no_sleep,
        )

        with pytest.raises(SafetyInterlockError):
            await validator.run(
                mission_plan=create_plan(),
                upload=False,
            )

        assert "download_mission_items" not in controller.calls

    asyncio.run(run_test())


def test_skipping_download_only_captures_snapshot() -> None:
    async def run_test() -> None:
        controller = FakeController()
        validator = FCSafeValidator(
            controller=controller,
            settle_time_s=0.0,
            sleep_function=no_sleep,
        )

        report = await validator.run(
            mission_plan=create_plan(),
            upload=False,
            verify_download=False,
        )

        assert report.verification is None
        assert report.download_performed is False
        assert "download_mission_items" not in controller.calls
        assert report.snapshot.hardware_uid == "ABC123"

    asyncio.run(run_test())


def test_validation_report_writes_json_and_csv(tmp_path) -> None:
    async def run_test() -> None:
        controller = FakeController()
        validator = FCSafeValidator(
            controller=controller,
            settle_time_s=0.0,
            sleep_function=no_sleep,
        )
        report = await validator.run(
            mission_plan=create_plan(),
            verify_download=True,
        )

        json_path, csv_path = write_validation_report(report, tmp_path)

        json_data = json.loads(json_path.read_text(encoding="utf-8"))
        with csv_path.open(encoding="utf-8-sig", newline="") as file:
            csv_rows = list(csv.DictReader(file))

        assert json_data["verification_passed"] is True
        assert csv_rows[0]["mission_name"] == "safe_validation_test"
        assert csv_rows[0]["armed"] == "False"

    asyncio.run(run_test())
