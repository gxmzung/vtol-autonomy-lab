from __future__ import annotations

import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from src.mission_plan import MissionPlan, Waypoint
from src.mission_raw_builder import build_raw_mission_items
from src.mission_raw_verifier import verify_downloaded_mission


def create_plan() -> MissionPlan:
    return MissionPlan(
        name="verification_test",
        waypoints=(
            Waypoint(
                "HOME",
                36.321,
                127.408,
                10.0,
                acceptance_radius_m=5.0,
                fly_through=False,
            ),
            Waypoint(
                "WPT1",
                36.322,
                127.409,
                20.0,
                acceptance_radius_m=8.0,
            ),
        ),
    )


def create_downloaded_items() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(**asdict(item))
        for item in build_raw_mission_items(create_plan())
    ]


def test_exact_downloaded_mission_matches() -> None:
    result = verify_downloaded_mission(
        mission_plan=create_plan(),
        downloaded_items=create_downloaded_items(),
    )

    assert result.matched is True
    assert result.mismatch_count == 0
    assert result.expected_count == 2
    assert result.actual_count == 2


def test_item_count_mismatch_is_detected() -> None:
    result = verify_downloaded_mission(
        mission_plan=create_plan(),
        downloaded_items=create_downloaded_items()[:1],
    )

    assert result.matched is False
    assert any(item.field == "item_count" for item in result.mismatches)


def test_coordinate_mismatch_is_detected() -> None:
    items = create_downloaded_items()
    items[1].x += 100

    result = verify_downloaded_mission(create_plan(), items)

    assert result.matched is False
    assert any(
        item.seq == 1 and item.field == "x"
        for item in result.mismatches
    )


def test_small_altitude_difference_is_accepted() -> None:
    items = create_downloaded_items()
    items[1].z += 0.04

    result = verify_downloaded_mission(
        create_plan(),
        items,
        altitude_tolerance_m=0.05,
    )

    assert result.matched is True


def test_large_altitude_difference_is_detected() -> None:
    items = create_downloaded_items()
    items[1].z += 0.20

    result = verify_downloaded_mission(
        create_plan(),
        items,
        altitude_tolerance_m=0.05,
    )

    assert result.matched is False
    assert any(item.field == "z" for item in result.mismatches)


def test_nan_yaw_mismatch_is_json_serializable() -> None:
    items = create_downloaded_items()
    items[0].param4 = 0.0

    result = verify_downloaded_mission(create_plan(), items)
    encoded = json.dumps(result.to_dict(), allow_nan=False)

    assert result.matched is False
    assert "param4" in encoded


def test_negative_tolerance_is_rejected() -> None:
    with pytest.raises(ValueError):
        verify_downloaded_mission(
            create_plan(),
            create_downloaded_items(),
            altitude_tolerance_m=-0.1,
        )
