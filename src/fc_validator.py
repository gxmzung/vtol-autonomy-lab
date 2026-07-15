from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from src.mavsdk_fc import MavsdkFlightController
from src.mission_plan import MissionPlan
from src.mission_raw_verifier import (
    MissionVerificationResult,
    verify_downloaded_mission,
)


class SafetyInterlockError(RuntimeError):
    """검증 중 기체가 Arm 또는 비행 상태일 때 발생한다."""


@dataclass(frozen=True, slots=True)
class VehicleSnapshot:
    connected: bool
    armed: bool
    in_air: bool
    health_ok: bool
    gps_fix: str
    satellites: int
    battery_remaining_pct: float
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    flight_mode: str
    vtol_state: str
    hardware_uid: str
    legacy_uid: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FCValidationReport:
    timestamp_utc: str
    connection_url: str
    mission_name: str
    upload_requested: bool
    upload_performed: bool
    download_performed: bool
    downloaded_items: int
    safety_passed: bool
    snapshot: VehicleSnapshot
    verification: MissionVerificationResult | None

    @property
    def verification_passed(self) -> bool:
        return bool(
            self.verification is not None
            and self.verification.matched
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp_utc": self.timestamp_utc,
            "connection_url": self.connection_url,
            "mission_name": self.mission_name,
            "upload_requested": self.upload_requested,
            "upload_performed": self.upload_performed,
            "download_performed": self.download_performed,
            "downloaded_items": self.downloaded_items,
            "safety_passed": self.safety_passed,
            "verification_passed": self.verification_passed,
            "snapshot": self.snapshot.to_dict(),
            "verification": (
                self.verification.to_dict()
                if self.verification is not None
                else None
            ),
        }


SleepFunction = Callable[[float], Awaitable[None]]


class FCSafeValidator:
    """Arm·이륙·임무시작 없이 FC 연결과 MissionRaw 저장 상태를 검증한다."""

    def __init__(
        self,
        controller: MavsdkFlightController,
        settle_time_s: float = 1.0,
        sleep_function: SleepFunction = asyncio.sleep,
    ) -> None:
        if settle_time_s < 0.0:
            raise ValueError("텔레메트리 대기시간은 0 이상이어야 합니다.")

        self._controller = controller
        self._settle_time_s = settle_time_s
        self._sleep = sleep_function

    async def _capture_snapshot(self) -> VehicleSnapshot:
        identification = await self._controller.get_vehicle_identification()
        context = self._controller.context

        return VehicleSnapshot(
            connected=bool(context.connected),
            armed=bool(context.armed),
            in_air=bool(context.in_air),
            health_ok=bool(context.health_ok),
            gps_fix=str(context.gps_fix),
            satellites=int(context.satellites),
            battery_remaining_pct=float(
                context.battery_remaining_pct
            ),
            latitude_deg=float(context.latitude_deg),
            longitude_deg=float(context.longitude_deg),
            altitude_m=float(context.altitude_m),
            flight_mode=str(context.flight_mode),
            vtol_state=str(context.vtol_state),
            hardware_uid=str(
                identification.get("hardware_uid", "")
            ),
            legacy_uid=int(
                identification.get("legacy_uid", 0)
            ),
        )

    @staticmethod
    def _enforce_safe_vehicle_state(
        snapshot: VehicleSnapshot,
    ) -> None:
        if snapshot.armed:
            raise SafetyInterlockError(
                "기체가 Arm 상태입니다. 임무 저장 검증을 중단합니다."
            )

        if snapshot.in_air:
            raise SafetyInterlockError(
                "기체가 비행 중입니다. 임무 저장 검증을 중단합니다."
            )

    async def run(
        self,
        mission_plan: MissionPlan,
        upload: bool = False,
        verify_download: bool = True,
        clear_existing: bool = True,
        stop_hold_time_s: float = 1.0,
    ) -> FCValidationReport:
        """FC 연결 후 안전 인터록을 확인하고 선택적으로 임무를 대조한다."""

        upload_performed = False
        download_performed = False
        downloaded_items: list[Any] = []
        verification: MissionVerificationResult | None = None

        try:
            await self._controller.connect()
            await self._sleep(self._settle_time_s)

            snapshot = await self._capture_snapshot()
            self._enforce_safe_vehicle_state(snapshot)

            if upload:
                await self._controller.upload_mission(
                    mission_plan=mission_plan,
                    clear_existing=clear_existing,
                    stop_hold_time_s=stop_hold_time_s,
                )
                upload_performed = True

            if verify_download:
                downloaded_items = (
                    await self._controller.download_mission_items()
                )
                download_performed = True
                verification = verify_downloaded_mission(
                    mission_plan=mission_plan,
                    downloaded_items=downloaded_items,
                    stop_hold_time_s=stop_hold_time_s,
                )

            return FCValidationReport(
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                connection_url=self._controller.connection_url,
                mission_name=mission_plan.name,
                upload_requested=upload,
                upload_performed=upload_performed,
                download_performed=download_performed,
                downloaded_items=len(downloaded_items),
                safety_passed=True,
                snapshot=snapshot,
                verification=verification,
            )

        finally:
            await self._controller.close()


def write_validation_report(
    report: FCValidationReport,
    output_directory: str | Path,
) -> tuple[Path, Path]:
    """검증 결과를 JSON과 1행 CSV로 저장한다."""

    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    safe_timestamp = report.timestamp_utc.replace(":", "-")
    stem = f"fc_validation_{safe_timestamp}"
    json_path = output_path / f"{stem}.json"
    csv_path = output_path / f"{stem}.csv"

    json_path.write_text(
        json.dumps(
            report.to_dict(),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )

    row = {
        "timestamp_utc": report.timestamp_utc,
        "connection_url": report.connection_url,
        "mission_name": report.mission_name,
        "safety_passed": report.safety_passed,
        "upload_requested": report.upload_requested,
        "upload_performed": report.upload_performed,
        "download_performed": report.download_performed,
        "downloaded_items": report.downloaded_items,
        "verification_passed": report.verification_passed,
        "connected": report.snapshot.connected,
        "armed": report.snapshot.armed,
        "in_air": report.snapshot.in_air,
        "health_ok": report.snapshot.health_ok,
        "gps_fix": report.snapshot.gps_fix,
        "satellites": report.snapshot.satellites,
        "battery_remaining_pct": (
            report.snapshot.battery_remaining_pct
        ),
        "latitude_deg": report.snapshot.latitude_deg,
        "longitude_deg": report.snapshot.longitude_deg,
        "altitude_m": report.snapshot.altitude_m,
        "flight_mode": report.snapshot.flight_mode,
        "vtol_state": report.snapshot.vtol_state,
        "hardware_uid": report.snapshot.hardware_uid,
        "legacy_uid": report.snapshot.legacy_uid,
        "mismatch_count": (
            report.verification.mismatch_count
            if report.verification is not None
            else 0
        ),
    }

    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    return json_path, csv_path
