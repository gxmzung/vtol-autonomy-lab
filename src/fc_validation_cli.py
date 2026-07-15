from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from src.fc_validator import (
    FCSafeValidator,
    SafetyInterlockError,
    write_validation_report,
)
from src.mavsdk_fc import MavsdkFlightController
from src.mission_manager import DEFAULT_MISSION_PATH, PROJECT_ROOT
from src.mission_plan import load_mission_plan


DEFAULT_OUTPUT_DIRECTORY = PROJECT_ROOT / "logs" / "fc_validation"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Arm·이륙·임무시작 없이 PX4 연결과 MissionRaw 저장 상태를 검증"
        )
    )

    parser.add_argument(
        "--connection-url",
        required=True,
        help=(
            "예: serial://COM5:57600 또는 udpin://0.0.0.0:14540"
        ),
    )
    parser.add_argument(
        "--mission-file",
        default=str(DEFAULT_MISSION_PATH),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIRECTORY),
    )
    parser.add_argument(
        "--connection-timeout",
        type=float,
        default=15.0,
    )
    parser.add_argument(
        "--settle-time",
        type=float,
        default=2.0,
        help="연결 후 텔레메트리 수신 대기시간(초)",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="안전 인터록 통과 후 임무를 저장만 함",
    )
    parser.add_argument(
        "--skip-download-verification",
        action="store_true",
        help="MissionRaw 다운로드 및 원본 대조를 생략",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="업로드 전에 기존 임무를 삭제하지 않음",
    )

    return parser


def parse_arguments(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    return build_parser().parse_args(argv)


async def run_cli(args: argparse.Namespace) -> int:
    mission_plan = load_mission_plan(args.mission_file)
    controller = MavsdkFlightController(
        connection_url=args.connection_url,
        connection_timeout_s=args.connection_timeout,
        mission_plan=mission_plan,
    )
    validator = FCSafeValidator(
        controller=controller,
        settle_time_s=args.settle_time,
    )

    print("=" * 68)
    print("PX4 안전 연결·MissionRaw 저장 검증")
    print(f"Connection: {args.connection_url}")
    print(f"Mission: {mission_plan.name}")
    print(f"Upload requested: {args.upload}")
    print("금지 명령: ARM / TAKEOFF / START MISSION / VTOL TRANSITION")
    print("=" * 68)

    try:
        report = await validator.run(
            mission_plan=mission_plan,
            upload=args.upload,
            verify_download=(
                not args.skip_download_verification
            ),
            clear_existing=not args.keep_existing,
        )
    except SafetyInterlockError as error:
        print(f"[SAFETY INTERLOCK] {error}")
        return 3
    except Exception as error:
        print(f"[VALIDATION ERROR] {type(error).__name__}: {error}")
        return 2

    json_path, csv_path = write_validation_report(
        report=report,
        output_directory=args.output_dir,
    )

    snapshot = report.snapshot
    print(f"Connected: {snapshot.connected}")
    print(f"Armed: {snapshot.armed}")
    print(f"In air: {snapshot.in_air}")
    print(f"Health OK: {snapshot.health_ok}")
    print(f"GPS: {snapshot.gps_fix} / satellites {snapshot.satellites}")
    print(f"Battery: {snapshot.battery_remaining_pct:.1f}%")
    print(f"Hardware UID: {snapshot.hardware_uid or 'UNKNOWN'}")
    print(f"Legacy UID: {snapshot.legacy_uid}")
    print(f"Mission uploaded: {report.upload_performed}")
    print(f"Downloaded items: {report.downloaded_items}")

    if report.verification is not None:
        print(
            "Mission verification: "
            f"{'PASS' if report.verification.matched else 'FAIL'}"
        )
        print(
            "Mission mismatches: "
            f"{report.verification.mismatch_count}"
        )

    print(f"JSON report: {json_path}")
    print(f"CSV report: {csv_path}")

    if (
        report.verification is not None
        and not report.verification.matched
    ):
        return 4

    return 0


def main(argv: list[str] | None = None) -> None:
    args = parse_arguments(argv)
    exit_code = asyncio.run(run_cli(args))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main(sys.argv[1:])
