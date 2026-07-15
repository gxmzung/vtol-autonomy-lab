import pytest

from src.target_filter import (
    ConstantVelocityKalman2D,
    TargetFilterConfig,
    TargetMeasurement,
)


def measurement(
    timestamp_s: float,
    north_m: float,
    east_m: float,
    confidence: float = 0.9,
) -> TargetMeasurement:
    return TargetMeasurement(
        timestamp_s=timestamp_s,
        north_m=north_m,
        east_m=east_m,
        confidence=confidence,
    )


def test_filter_initializes_from_first_valid_measurement() -> None:
    target_filter = ConstantVelocityKalman2D()

    estimate = target_filter.update(
        measurement(0.0, 10.0, -3.0)
    )

    assert estimate.initialized is True
    assert estimate.measurement_accepted is True
    assert estimate.north_m == pytest.approx(10.0)
    assert estimate.east_m == pytest.approx(-3.0)


def test_filter_rejects_low_confidence_before_initialization() -> None:
    target_filter = ConstantVelocityKalman2D()

    estimate = target_filter.update(
        measurement(
            0.0,
            10.0,
            -3.0,
            confidence=0.2,
        )
    )

    assert estimate.initialized is False
    assert estimate.measurement_accepted is False


def test_filter_estimates_constant_velocity() -> None:
    config = TargetFilterConfig(
        measurement_std_m=0.2,
        stable_position_std_m=3.0,
    )
    target_filter = ConstantVelocityKalman2D(config)

    target_filter.update(measurement(0.0, 0.0, 0.0))
    target_filter.update(measurement(1.0, 2.0, -1.0))
    target_filter.update(measurement(2.0, 4.0, -2.0))
    estimate = target_filter.update(
        measurement(3.0, 6.0, -3.0)
    )

    assert estimate.velocity_north_m_s == pytest.approx(
        2.0,
        abs=0.7,
    )
    assert estimate.velocity_east_m_s == pytest.approx(
        -1.0,
        abs=0.7,
    )


def test_filter_rejects_large_outlier() -> None:
    config = TargetFilterConfig(
        measurement_std_m=0.5,
        innovation_gate_sigma=3.0,
    )
    target_filter = ConstantVelocityKalman2D(config)

    target_filter.update(measurement(0.0, 0.0, 0.0))
    target_filter.update(measurement(1.0, 1.0, 0.0))
    estimate = target_filter.update(
        measurement(2.0, 100.0, -100.0)
    )

    assert estimate.measurement_accepted is False
    assert estimate.prediction_only is True
    assert estimate.north_m < 10.0
    assert estimate.east_m > -10.0


def test_filter_predicts_during_short_dropout() -> None:
    target_filter = ConstantVelocityKalman2D()

    target_filter.update(measurement(0.0, 0.0, 0.0))
    target_filter.update(measurement(1.0, 1.0, 0.0))

    estimate = target_filter.predict(1.5)

    assert estimate.initialized is True
    assert estimate.prediction_only is True
    assert estimate.stale is False


def test_filter_marks_long_prediction_as_stale() -> None:
    config = TargetFilterConfig(
        max_prediction_s=1.0,
    )
    target_filter = ConstantVelocityKalman2D(config)

    target_filter.update(measurement(0.0, 0.0, 0.0))
    estimate = target_filter.predict(1.1)

    assert estimate.stale is True
    assert estimate.tracking_stable is False


def test_filter_rejects_out_of_order_measurement() -> None:
    target_filter = ConstantVelocityKalman2D()

    target_filter.update(measurement(2.0, 0.0, 0.0))

    with pytest.raises(ValueError):
        target_filter.update(
            measurement(1.0, 1.0, 1.0)
        )


def test_filter_becomes_stable_after_consistent_updates() -> None:
    config = TargetFilterConfig(
        measurement_std_m=0.2,
        stable_position_std_m=3.0,
        stable_after_accepted_count=3,
    )
    target_filter = ConstantVelocityKalman2D(config)

    target_filter.update(measurement(0.0, 10.0, 2.0))
    target_filter.update(measurement(1.0, 10.0, 2.0))
    estimate = target_filter.update(
        measurement(2.0, 10.0, 2.0)
    )

    assert estimate.tracking_stable is True


def test_filter_reset_clears_state() -> None:
    target_filter = ConstantVelocityKalman2D()

    target_filter.update(measurement(0.0, 5.0, 1.0))
    target_filter.reset()

    estimate = target_filter.predict(1.0)

    assert estimate.initialized is False
    assert estimate.confidence == 0.0


def test_invalid_measurement_confidence_raises() -> None:
    with pytest.raises(ValueError):
        TargetMeasurement(
            timestamp_s=0.0,
            north_m=0.0,
            east_m=0.0,
            confidence=1.1,
        )
