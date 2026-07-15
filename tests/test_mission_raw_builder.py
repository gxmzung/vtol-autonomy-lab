import math

import pytest

from src.mission_plan import MissionPlan, Waypoint
from src.mission_raw_builder import (
    COORDINATE_SCALE,
    MAV_CMD_NAV_WAYPOINT,
    MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
    MAV_MISSION_TYPE_MISSION,
    RawMissionItemData,
    build_mavsdk_mission_items,
    build_raw_mission_items,
    build_raw_waypoint_item,
    encode_coordinate_deg,
)


def create_plan() -> MissionPlan:
    return MissionPlan(
        name="raw_test",
        waypoints=(
            Waypoint(
                name="HOME",
                latitude_deg=36.321,
                longitude_deg=127.408,
                relative_altitude_m=10.0,
                acceptance_radius_m=5.0,
                fly_through=False,
            ),
            Waypoint(
                name="WPT1",
                latitude_deg=36.322,
                longitude_deg=127.409,
                relative_altitude_m=25.0,
                acceptance_radius_m=8.0,
                fly_through=True,
            ),
        ),
    )


def test_encode_coordinate_uses_1e7_scale() -> None:
    assert encode_coordinate_deg(36.321) == round(36.321 * COORDINATE_SCALE)
    assert encode_coordinate_deg(127.408) == round(127.408 * COORDINATE_SCALE)


def test_build_raw_items_assigns_sequence_and_current() -> None:
    items = build_raw_mission_items(create_plan())

    assert [item.seq for item in items] == [0, 1]
    assert [item.current for item in items] == [1, 0]
    assert all(item.autocontinue == 1 for item in items)


def test_build_raw_items_uses_expected_mavlink_constants() -> None:
    items = build_raw_mission_items(create_plan())

    assert all(item.frame == MAV_FRAME_GLOBAL_RELATIVE_ALT_INT for item in items)
    assert all(item.command == MAV_CMD_NAV_WAYPOINT for item in items)
    assert all(item.mission_type == MAV_MISSION_TYPE_MISSION for item in items)


def test_waypoint_fields_are_encoded() -> None:
    plan = create_plan()
    items = build_raw_mission_items(plan)

    assert items[1].x == round(plan.waypoints[1].latitude_deg * COORDINATE_SCALE)
    assert items[1].y == round(plan.waypoints[1].longitude_deg * COORDINATE_SCALE)
    assert items[1].z == 25.0
    assert items[1].param2 == 8.0
    assert math.isnan(items[1].param4)


def test_non_fly_through_waypoint_gets_hold_time() -> None:
    items = build_raw_mission_items(create_plan(), stop_hold_time_s=2.5)

    assert items[0].param1 == 2.5
    assert items[1].param1 == 0.0


def test_negative_stop_hold_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_raw_waypoint_item(
            waypoint=create_plan().waypoints[0],
            seq=0,
            is_current=True,
            stop_hold_time_s=-1.0,
        )


def test_to_mavsdk_item_preserves_constructor_order() -> None:
    captured: list[tuple[object, ...]] = []

    def fake_factory(*args):
        captured.append(args)
        return args

    item = RawMissionItemData(
        seq=3,
        frame=6,
        command=16,
        current=0,
        autocontinue=1,
        param1=0.0,
        param2=5.0,
        param3=0.0,
        param4=float("nan"),
        x=363210000,
        y=1274080000,
        z=20.0,
        mission_type=0,
    )

    result = item.to_mavsdk_item(item_factory=fake_factory)

    assert result == captured[0]
    assert captured[0][0:5] == (3, 6, 16, 0, 1)
    assert captured[0][9:13] == (363210000, 1274080000, 20.0, 0)


def test_build_mavsdk_items_uses_factory_for_every_item() -> None:
    def fake_factory(*args):
        return {"seq": args[0], "x": args[9], "y": args[10]}

    items = build_mavsdk_mission_items(create_plan(), item_factory=fake_factory)

    assert items == [
        {"seq": 0, "x": 363210000, "y": 1274080000},
        {"seq": 1, "x": 363220000, "y": 1274090000},
    ]
