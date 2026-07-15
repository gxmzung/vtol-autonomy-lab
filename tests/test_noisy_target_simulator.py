import pytest

from src.noisy_target_simulator import (
    NoisyTargetSimulator,
)


def test_simulator_advances_true_target() -> None:
    simulator = NoisyTargetSimulator(
        initial_north_m=10.0,
        initial_east_m=2.0,
        velocity_north_m_s=-2.0,
        velocity_east_m_s=1.0,
        measurement_std_m=0.0,
    )

    state, measurement = simulator.step(0.5)

    assert state.north_m == pytest.approx(9.0)
    assert state.east_m == pytest.approx(2.5)
    assert measurement is not None
    assert measurement.north_m == pytest.approx(9.0)
    assert measurement.east_m == pytest.approx(2.5)


def test_simulator_is_deterministic_with_same_seed() -> None:
    first = NoisyTargetSimulator(seed=123)
    second = NoisyTargetSimulator(seed=123)

    _, first_measurement = first.step(0.2)
    _, second_measurement = second.step(0.2)

    assert first_measurement == second_measurement


def test_simulator_can_force_dropout() -> None:
    simulator = NoisyTargetSimulator()

    _, measurement = simulator.step(
        0.2,
        force_dropout=True,
    )

    assert measurement is None


def test_simulator_can_force_outlier() -> None:
    simulator = NoisyTargetSimulator(
        measurement_std_m=0.0,
        outlier_magnitude_m=25.0,
    )

    state, measurement = simulator.step(
        0.2,
        force_outlier=True,
    )

    assert measurement is not None
    assert measurement.north_m == pytest.approx(
        state.north_m + 25.0
    )
    assert measurement.east_m == pytest.approx(
        state.east_m - 25.0
    )
