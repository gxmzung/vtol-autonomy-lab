import json

import pytest

from src.mission_plan import (
    MissionPlan,
    Waypoint,
    WaypointNavigator,
    haversine_distance_m,
    load_mission_plan,
)


def create_test_plan() -> MissionPlan:
    return MissionPlan(
        name="test_mission",
        waypoints=(
            Waypoint(
                name="HOME",
                latitude_deg=36.3210,
                longitude_deg=127.4080,
                relative_altitude_m=10.0,
                acceptance_radius_m=5.0,
            ),
            Waypoint(
                name="WPT1",
                latitude_deg=36.3211,
                longitude_deg=127.4081,
                relative_altitude_m=20.0,
                acceptance_radius_m=5.0,
            ),
        ),
    )


def test_waypoint_rejects_invalid_latitude() -> None:
    with pytest.raises(ValueError):
        Waypoint(
            name="INVALID",
            latitude_deg=91.0,
            longitude_deg=127.0,
            relative_altitude_m=10.0,
        )


def test_waypoint_rejects_negative_altitude() -> None:
    with pytest.raises(ValueError):
        Waypoint(
            name="INVALID",
            latitude_deg=36.0,
            longitude_deg=127.0,
            relative_altitude_m=-1.0,
        )


def test_mission_requires_two_waypoints() -> None:
    with pytest.raises(ValueError):
        MissionPlan(
            name="invalid_mission",
            waypoints=(
                Waypoint(
                    name="HOME",
                    latitude_deg=36.0,
                    longitude_deg=127.0,
                    relative_altitude_m=10.0,
                ),
            ),
        )


def test_mission_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError):
        MissionPlan(
            name="duplicate_mission",
            waypoints=(
                Waypoint(
                    name="WPT1",
                    latitude_deg=36.0,
                    longitude_deg=127.0,
                    relative_altitude_m=10.0,
                ),
                Waypoint(
                    name="WPT1",
                    latitude_deg=36.1,
                    longitude_deg=127.1,
                    relative_altitude_m=20.0,
                ),
            ),
        )


def test_haversine_same_position_is_zero() -> None:
    distance_m = haversine_distance_m(
        latitude_a_deg=36.321,
        longitude_a_deg=127.408,
        latitude_b_deg=36.321,
        longitude_b_deg=127.408,
    )
    assert distance_m == pytest.approx(0.0, abs=0.001)


def test_navigator_advances_at_waypoint() -> None:
    navigator = WaypointNavigator(create_test_plan())
    result = navigator.update_position(
        latitude_deg=36.3210,
        longitude_deg=127.4080,
    )
    assert result.waypoint_reached is True
    assert result.advanced is True
    assert result.mission_completed is False
    assert navigator.current_waypoint.name == "WPT1"
    assert result.progress_pct == 50.0


def test_navigator_completes_final_waypoint() -> None:
    navigator = WaypointNavigator(create_test_plan())
    navigator.update_position(latitude_deg=36.3210, longitude_deg=127.4080)
    result = navigator.update_position(latitude_deg=36.3211, longitude_deg=127.4081)
    assert result.waypoint_reached is True
    assert result.mission_completed is True
    assert result.progress_pct == 100.0
    assert navigator.completed is True


def test_load_mission_plan_from_json(tmp_path) -> None:
    mission_path = tmp_path / "mission.json"
    mission_data = {
        "name": "json_test",
        "waypoints": [
            {
                "name": "HOME",
                "latitude_deg": 36.321,
                "longitude_deg": 127.408,
                "relative_altitude_m": 10.0,
            },
            {
                "name": "WPT1",
                "latitude_deg": 36.322,
                "longitude_deg": 127.409,
                "relative_altitude_m": 20.0,
            },
        ],
    }
    mission_path.write_text(json.dumps(mission_data), encoding="utf-8")
    mission_plan = load_mission_plan(mission_path)
    assert mission_plan.name == "json_test"
    assert mission_plan.total_waypoints == 2
    assert mission_plan.waypoints[1].name == "WPT1"
