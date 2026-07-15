import pytest

from src.target_estimate import TargetEstimate


def test_target_distance_and_bearing() -> None:
    target = TargetEstimate(
        relative_north_m=3.0,
        relative_east_m=4.0,
        confidence=0.9,
        tracking_stable=True,
        timestamp_s=10.0,
    )

    assert target.horizontal_distance_m == pytest.approx(5.0)
    assert target.bearing_deg == pytest.approx(53.130102, abs=1e-6)


def test_target_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError):
        TargetEstimate(
            relative_north_m=1.0,
            relative_east_m=1.0,
            confidence=1.1,
            tracking_stable=True,
            timestamp_s=0.0,
        )


def test_target_age_does_not_become_negative() -> None:
    target = TargetEstimate(
        relative_north_m=0.0,
        relative_east_m=0.0,
        confidence=1.0,
        tracking_stable=True,
        timestamp_s=10.0,
    )

    assert target.age_s(9.0) == 0.0


def test_target_alignment_uses_horizontal_and_vertical_tolerance() -> None:
    target = TargetEstimate(
        relative_north_m=0.5,
        relative_east_m=0.5,
        relative_down_m=0.4,
        confidence=1.0,
        tracking_stable=True,
        timestamp_s=0.0,
    )

    assert target.is_aligned(1.0, 0.5) is True
    assert target.is_aligned(0.5, 0.5) is False
