import asyncio

import pytest

from src.mission_manager import DEFAULT_MISSION_PATH, run_mission_async
from src.mission_plan import haversine_distance_m, load_mission_plan
from src.state_machine import FailureCode, MissionState
from src.virtual_fc import SimulationScenario, VirtualFlightController


def run_navigation_mission():
    mission_plan = load_mission_plan(DEFAULT_MISSION_PATH)
    controller = VirtualFlightController(
        scenario=SimulationScenario.NORMAL,
        mission_plan=mission_plan,
    )
    result = asyncio.run(
        run_mission_async(
            flight_controller=controller,
            dt_s=0.25,
            max_duration_s=60.0,
            realtime=False,
        )
    )
    return mission_plan, controller, result


def test_virtual_navigation_completes() -> None:
    _, controller, result = run_navigation_mission()
    assert result.state_machine.state is MissionState.COMPLETE
    assert result.state_machine.failure_code is FailureCode.NONE
    assert controller.context.navigation_complete is True


def test_virtual_navigation_reaches_all_waypoints() -> None:
    mission_plan, controller, _ = run_navigation_mission()
    assert controller.navigator is not None
    expected_waypoint_names = [waypoint.name for waypoint in mission_plan.waypoints]
    assert controller.navigator.reached_waypoint_names == expected_waypoint_names


def test_virtual_navigation_finishes_at_home() -> None:
    mission_plan, controller, _ = run_navigation_mission()
    final_waypoint = mission_plan.waypoints[-1]
    distance_to_home_m = haversine_distance_m(
        latitude_a_deg=controller.context.latitude_deg,
        longitude_a_deg=controller.context.longitude_deg,
        latitude_b_deg=final_waypoint.latitude_deg,
        longitude_b_deg=final_waypoint.longitude_deg,
    )
    assert distance_to_home_m <= final_waypoint.acceptance_radius_m
    assert controller.context.returned_home is True
    assert controller.context.navigation_complete is True


def test_waypoint_progress_is_monotonic() -> None:
    _, _, result = run_navigation_mission()
    progress_values = [
        float(row["waypoint_progress_pct"])
        for row in result.telemetry_rows
    ]
    assert progress_values == sorted(progress_values)
    assert progress_values[-1] == pytest.approx(100.0)
