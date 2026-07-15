import asyncio

import pytest

from src.hybrid_mission_controller import HybridMode
from src.hybrid_mission_simulator import (
    HybridSimulationScenario,
    VirtualHybridFlightController,
    VirtualTargetModel,
    run_hybrid_simulation_async,
)
from src.offboard_controller import VelocityNedCommand


def run_scenario(
    scenario: HybridSimulationScenario,
):
    return asyncio.run(
        run_hybrid_simulation_async(
            scenario=scenario,
            dt_s=0.25,
            max_duration_s=30.0,
        )
    )


def test_normal_hybrid_flow_aligns_and_returns_home() -> None:
    result = run_scenario(HybridSimulationScenario.NORMAL)

    assert result.final_mode is HybridMode.RTL
    assert result.target_aligned is True
    assert result.returned_home is True
    assert result.completed_safely is True


def test_normal_flow_contains_all_major_modes() -> None:
    result = run_scenario(HybridSimulationScenario.NORMAL)
    modes = [transition.current_mode for transition in result.transitions]

    assert HybridMode.WAITING_FOR_MULTICOPTER in modes
    assert HybridMode.OFFBOARD_APPROACH in modes
    assert HybridMode.TARGET_ALIGNED in modes
    assert HybridMode.RTL in modes


def test_normal_flow_sends_pause_transition_offboard_and_rtl() -> None:
    result = run_scenario(HybridSimulationScenario.NORMAL)
    offboard_call_names = [name for name, _ in result.offboard_calls]

    assert result.flight_controller_calls[:2] == [
        "pause_uploaded_mission",
        "transition_to_multicopter",
    ]
    assert "start" in offboard_call_names
    assert "stop" in offboard_call_names
    assert result.flight_controller_calls[-1] == "return_to_launch"


def test_target_distance_decreases_during_offboard() -> None:
    result = run_scenario(HybridSimulationScenario.NORMAL)
    distances = [
        float(row["target_distance_m"])
        for row in result.telemetry_rows
        if row["hybrid_mode"] == HybridMode.OFFBOARD_APPROACH.value
    ]

    assert len(distances) >= 3
    assert distances[-1] < distances[0]


def test_low_confidence_is_rejected_before_pause() -> None:
    result = run_scenario(HybridSimulationScenario.LOW_CONFIDENCE)

    assert result.final_mode is HybridMode.MISSION_RAW
    assert result.rejected_before_pause is True
    assert result.flight_controller_calls == []
    assert result.offboard_calls == []


def test_tracking_loss_stops_offboard_and_uses_rtl() -> None:
    result = run_scenario(HybridSimulationScenario.TRACKING_LOSS)

    assert result.final_mode is HybridMode.RTL
    assert result.target_aligned is False
    assert result.returned_home is True
    assert any(
        "표적 추적" in transition.reason
        for transition in result.transitions
    )


def test_failsafe_during_approach_uses_rtl() -> None:
    result = run_scenario(
        HybridSimulationScenario.FAILSAFE_DURING_APPROACH
    )

    assert result.final_mode is HybridMode.RTL
    assert result.returned_home is True
    assert result.target_aligned is False
    assert any(
        "Failsafe" in transition.reason
        for transition in result.transitions
    )


def test_transition_timeout_uses_rtl_without_starting_offboard() -> None:
    result = run_scenario(HybridSimulationScenario.TRANSITION_TIMEOUT)
    offboard_call_names = [name for name, _ in result.offboard_calls]

    assert result.final_mode is HybridMode.RTL
    assert result.returned_home is True
    assert "start" not in offboard_call_names
    assert any(
        "역천이 제한시간" in transition.reason
        for transition in result.transitions
    )


def test_simulator_rejects_invalid_timing_values() -> None:
    with pytest.raises(ValueError):
        asyncio.run(run_hybrid_simulation_async(dt_s=0.0))

    with pytest.raises(ValueError):
        asyncio.run(run_hybrid_simulation_async(max_duration_s=0.0))

    with pytest.raises(ValueError):
        asyncio.run(run_hybrid_simulation_async(aligned_hold_s=-1.0))


def test_virtual_target_model_applies_ned_command() -> None:
    model = VirtualTargetModel(
        relative_north_m=10.0,
        relative_east_m=-2.0,
        relative_down_m=1.0,
    )
    model.apply_command(
        VelocityNedCommand(
            north_m_s=2.0,
            east_m_s=-1.0,
            down_m_s=0.5,
            yaw_deg=0.0,
        ),
        dt_s=1.0,
    )

    assert model.relative_north_m == pytest.approx(8.0)
    assert model.relative_east_m == pytest.approx(-1.0)
    assert model.relative_down_m == pytest.approx(0.5)


def test_virtual_hybrid_fc_completes_back_transition() -> None:
    async def run_test() -> None:
        fc = VirtualHybridFlightController(
            scenario=HybridSimulationScenario.NORMAL,
            transition_duration_s=1.0,
        )
        await fc.transition_to_multicopter()
        fc.step(0.5)
        assert fc.context.vtol_state == "TRANSITION_TO_MC"
        fc.step(0.5)
        assert fc.context.vtol_state == "MC"

    asyncio.run(run_test())
