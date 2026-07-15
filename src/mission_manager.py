from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.event_logger import write_telemetry_log, write_transition_log
from src.failsafe_supervisor import FailsafeSupervisor
from src.hybrid_mission_simulator import (
    HybridSimulationScenario,
    run_hybrid_simulation_async,
    save_hybrid_simulation_log,
)
from src.flight_controller import FlightControllerInterface
from src.mavsdk_fc import MavsdkFlightController
from src.mission_context import MissionContext
from src.mission_plan import MissionPlan, load_mission_plan
from src.state_machine import MissionState, MissionStateMachine
from src.virtual_fc import SimulationScenario, VirtualFlightController


BackendName = Literal["virtual", "mavsdk"]
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MISSION_PATH = PROJECT_ROOT / "config" / "mission.json"


@dataclass(slots=True)
class SimulationResult:
    state_machine: MissionStateMachine
    telemetry_rows: list[dict[str, object]]
    duration_s: float


def create_flight_controller(
    backend: BackendName,
    scenario: SimulationScenario = SimulationScenario.NORMAL,
    connection_url: str = "udpin://0.0.0.0:14540",
    takeoff_altitude_m: float = 10.0,
    mission_plan: MissionPlan | None = None,
) -> FlightControllerInterface:
    if takeoff_altitude_m <= 0:
        raise ValueError("이륙 고도는 0보다 커야 합니다.")

    if backend == "virtual":
        return VirtualFlightController(
            scenario=scenario,
            takeoff_altitude_m=takeoff_altitude_m,
            mission_plan=mission_plan,
        )

    if backend == "mavsdk":
        return MavsdkFlightController(
            connection_url=connection_url,
            mission_plan=mission_plan,
        )

    raise ValueError(f"지원하지 않는 backend입니다: {backend}")


async def dispatch_state_entry_command(
    flight_controller: FlightControllerInterface,
    state: MissionState,
    takeoff_altitude_m: float,
) -> None:
    if state is MissionState.ARMING:
        await flight_controller.arm()
    elif state is MissionState.TAKEOFF:
        await flight_controller.takeoff(altitude_m=takeoff_altitude_m)
    elif state is MissionState.FORWARD_TRANSITION:
        await flight_controller.transition_to_fixed_wing()
    elif state is MissionState.BACK_TRANSITION:
        await flight_controller.transition_to_multicopter()
    elif state is MissionState.RETURN_HOME:
        await flight_controller.return_to_launch()
    elif state is MissionState.LAND:
        await flight_controller.land()


def create_telemetry_row(
    now_s: float,
    state: MissionState,
    context: MissionContext,
    machine: MissionStateMachine,
) -> dict[str, object]:
    return {
        "time_s": f"{now_s:.2f}",
        "state": state.name,
        "connected": context.connected,
        "health_ok": context.health_ok,
        "armed": context.armed,
        "in_air": context.in_air,
        "altitude_m": f"{context.altitude_m:.2f}",
        "airspeed_m_s": f"{context.airspeed_m_s:.2f}",
        "latitude_deg": f"{context.latitude_deg:.7f}",
        "longitude_deg": f"{context.longitude_deg:.7f}",
        "battery_remaining_pct": f"{context.battery_remaining_pct:.1f}",
        "gps_fix": context.gps_fix,
        "satellites": context.satellites,
        "flight_mode": context.flight_mode,
        "vtol_state": context.vtol_state,
        "current_waypoint_name": context.current_waypoint_name,
        "waypoint_index": context.waypoint_index,
        "waypoint_progress_pct": f"{context.waypoint_progress_pct:.2f}",
        "distance_to_waypoint_m": f"{context.distance_to_waypoint_m:.2f}",
        "navigation_complete": context.navigation_complete,
        "mission_uploaded": context.mission_uploaded,
        "mission_started": context.mission_started,
        "mission_paused": context.mission_paused,
        "raw_mission_current": context.raw_mission_current,
        "raw_mission_total": context.raw_mission_total,
        "raw_mission_progress_pct": f"{context.raw_mission_progress_pct:.2f}",
        "raw_mission_finished": context.raw_mission_finished,
        "target_detected": context.target_detected,
        "search_complete": context.search_complete,
        "returned_home": context.returned_home,
        "landed": context.landed,
        "failsafe_triggered": context.failsafe_triggered,
        "failsafe_code": context.failsafe_code,
        "failsafe_reason": context.failsafe_reason,
        "failsafe_action": context.failsafe_action,
        "failure_code": machine.failure_code.name,
    }


async def run_mission_async(
    flight_controller: FlightControllerInterface,
    dt_s: float = 0.25,
    max_duration_s: float = 60.0,
    takeoff_altitude_m: float = 10.0,
    realtime: bool = False,
    failsafe_supervisor: FailsafeSupervisor | None = None,
) -> SimulationResult:
    if dt_s <= 0:
        raise ValueError("갱신 간격은 0보다 커야 합니다.")
    if max_duration_s <= 0:
        raise ValueError("최대 실행시간은 0보다 커야 합니다.")

    machine = MissionStateMachine(takeoff_altitude_m=takeoff_altitude_m)
    supervisor = failsafe_supervisor or FailsafeSupervisor()
    telemetry_rows: list[dict[str, object]] = []
    now_s = 0.0

    try:
        await flight_controller.connect()

        while now_s < max_duration_s:
            if realtime:
                await asyncio.sleep(dt_s)

            now_s = round(now_s + dt_s, 6)
            context = await flight_controller.update(
                state=machine.state,
                dt_s=dt_s,
                state_elapsed_s=machine.state_elapsed(now_s),
            )

            supervisor.apply(context=context, state=machine.state)
            previous_state = machine.state
            current_state = machine.update(context=context, now_s=now_s)

            telemetry_rows.append(
                create_telemetry_row(
                    now_s=now_s,
                    state=current_state,
                    context=context,
                    machine=machine,
                )
            )

            if previous_state is not current_state:
                print(f"[{now_s:6.2f}s] {previous_state.name} -> {current_state.name}")
                if machine.history:
                    print(f"           {machine.history[-1].reason}")

                if current_state not in {MissionState.COMPLETE, MissionState.ABORT}:
                    try:
                        await dispatch_state_entry_command(
                            flight_controller=flight_controller,
                            state=current_state,
                            takeoff_altitude_m=takeoff_altitude_m,
                        )
                    except Exception as error:
                        context.failsafe_triggered = True
                        context.failsafe_code = "EXTERNAL_FAILSAFE"
                        context.failsafe_reason = f"{type(error).__name__}: {error}"
                        context.failsafe_action = "ABORT"
                        print(
                            "[COMMAND ERROR] "
                            f"{current_state.name}: {type(error).__name__}: {error}"
                        )

            if current_state in {MissionState.COMPLETE, MissionState.ABORT}:
                break

        return SimulationResult(
            state_machine=machine,
            telemetry_rows=telemetry_rows,
            duration_s=now_s,
        )

    finally:
        await flight_controller.close()


async def run_simulation_async(
    scenario: SimulationScenario,
    dt_s: float = 0.25,
    max_duration_s: float = 60.0,
) -> SimulationResult:
    mission_plan = load_mission_plan(DEFAULT_MISSION_PATH)
    controller = create_flight_controller(
        backend="virtual",
        scenario=scenario,
        mission_plan=mission_plan,
    )
    return await run_mission_async(
        flight_controller=controller,
        dt_s=dt_s,
        max_duration_s=max_duration_s,
        realtime=False,
    )


def run_simulation(
    scenario: SimulationScenario,
    dt_s: float = 0.25,
    max_duration_s: float = 60.0,
) -> SimulationResult:
    return asyncio.run(
        run_simulation_async(
            scenario=scenario,
            dt_s=dt_s,
            max_duration_s=max_duration_s,
        )
    )


def save_result_logs(
    result: SimulationResult,
    log_name: str,
) -> tuple[Path, Path]:
    log_directory = PROJECT_ROOT / "logs"
    transition_path = write_transition_log(
        records=result.state_machine.history,
        output_path=log_directory / f"transitions_{log_name}.csv",
    )
    telemetry_path = write_telemetry_log(
        rows=result.telemetry_rows,
        output_path=log_directory / f"telemetry_{log_name}.csv",
    )
    return transition_path, telemetry_path


async def main_async(args: argparse.Namespace) -> None:
    if args.hybrid_demo:
        hybrid_scenario = HybridSimulationScenario(args.hybrid_scenario)
        print("=" * 60)
        print("VTOL 하이브리드 임무 통합 시뮬레이션")
        print(f"Scenario: {hybrid_scenario.value}")
        print("Flow: MissionRaw -> MC transition -> Offboard -> RTL")
        print("=" * 60)

        result = await run_hybrid_simulation_async(
            scenario=hybrid_scenario,
            dt_s=args.dt,
            max_duration_s=args.max_duration,
        )
        log_path = save_hybrid_simulation_log(
            result=result,
            output_path=(
                PROJECT_ROOT
                / "logs"
                / "hybrid"
                / f"hybrid_{hybrid_scenario.value}.csv"
            ),
        )

        print("=" * 60)
        print(f"최종 하이브리드 모드: {result.final_mode.value}")
        print(f"표적 정렬 완료: {result.target_aligned}")
        print(f"RTL 복귀 완료: {result.returned_home}")
        print(f"안전 완료: {result.completed_safely}")
        print(f"실행 시간: {result.duration_s:.2f}초")
        print(f"통합 로그: {log_path}")
        print("=" * 60)
        return

    scenario = SimulationScenario(args.scenario)
    mission_plan = load_mission_plan(args.mission_file)
    controller = create_flight_controller(
        backend=args.backend,
        scenario=scenario,
        connection_url=args.connection_url,
        takeoff_altitude_m=args.takeoff_altitude,
        mission_plan=mission_plan,
    )

    print("=" * 60)
    print("VTOL 자율임무 실행")
    print(f"Backend: {args.backend}")
    print(f"Mission: {mission_plan.name}")
    print(f"Waypoints: {mission_plan.total_waypoints}")
    if args.backend == "virtual":
        print(f"Scenario: {scenario.value}")
    else:
        print(f"Connection: {args.connection_url}")
    print("=" * 60)

    result = await run_mission_async(
        flight_controller=controller,
        dt_s=args.dt,
        max_duration_s=args.max_duration,
        takeoff_altitude_m=args.takeoff_altitude,
        realtime=args.backend == "mavsdk",
    )

    log_name = scenario.value if args.backend == "virtual" else "mavsdk"
    transition_path, telemetry_path = save_result_logs(result=result, log_name=log_name)

    print("=" * 60)
    print(f"최종 상태: {result.state_machine.state.name}")
    print(f"실패 코드: {result.state_machine.failure_code.name}")
    print(f"실행 시간: {result.duration_s:.2f}초")
    print(f"상태 로그: {transition_path}")
    print(f"비행 로그: {telemetry_path}")
    print("=" * 60)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="VTOL 자율임무 관리자")
    parser.add_argument("--backend", choices=["virtual", "mavsdk"], default="virtual")
    parser.add_argument(
        "--scenario",
        choices=[scenario.value for scenario in SimulationScenario],
        default=SimulationScenario.NORMAL.value,
    )
    parser.add_argument("--mission-file", default=str(DEFAULT_MISSION_PATH))
    parser.add_argument("--connection-url", default="udpin://0.0.0.0:14540")
    parser.add_argument("--takeoff-altitude", type=float, default=10.0)
    parser.add_argument("--dt", type=float, default=0.25)
    parser.add_argument("--max-duration", type=float, default=60.0)
    parser.add_argument(
        "--hybrid-demo",
        action="store_true",
        help="MissionRaw-Offboard-RTL 통합 가상시험 실행",
    )
    parser.add_argument(
        "--hybrid-scenario",
        choices=[scenario.value for scenario in HybridSimulationScenario],
        default=HybridSimulationScenario.NORMAL.value,
        help="하이브리드 통합시험 고장 주입 시나리오",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n[STOP] 사용자에 의해 실행이 중단되었습니다.")
    except Exception as error:
        print(f"\n[ERROR] {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()
