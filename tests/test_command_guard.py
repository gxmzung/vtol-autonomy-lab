from src.command_guard import CommandGuard, GuardCode
from src.mission_context import MissionContext
from src.target_estimate import TargetEstimate


def create_context() -> MissionContext:
    return MissionContext(
        connected=True,
        in_air=True,
        mission_started=True,
        mission_paused=True,
        vtol_state="MC",
    )


def create_target(**overrides) -> TargetEstimate:
    values = {
        "relative_north_m": 10.0,
        "relative_east_m": 2.0,
        "confidence": 0.9,
        "tracking_stable": True,
        "timestamp_s": 10.0,
    }
    values.update(overrides)
    return TargetEstimate(**values)


def test_guard_allows_valid_offboard_entry() -> None:
    result = CommandGuard().evaluate_offboard_entry(
        create_context(),
        create_target(),
        now_s=10.5,
    )
    assert result.allowed is True
    assert result.code is GuardCode.OK


def test_guard_rejects_low_confidence() -> None:
    result = CommandGuard().evaluate_target(
        create_target(confidence=0.5),
        now_s=10.5,
    )
    assert result.code is GuardCode.LOW_CONFIDENCE


def test_guard_rejects_unstable_tracking() -> None:
    result = CommandGuard().evaluate_target(
        create_target(tracking_stable=False),
        now_s=10.5,
    )
    assert result.code is GuardCode.TRACKING_UNSTABLE


def test_guard_rejects_stale_target() -> None:
    result = CommandGuard().evaluate_target(
        create_target(timestamp_s=1.0),
        now_s=10.0,
    )
    assert result.code is GuardCode.STALE_TARGET


def test_guard_rejects_failsafe() -> None:
    context = create_context()
    context.failsafe_triggered = True
    result = CommandGuard().evaluate_vehicle(context)
    assert result.code is GuardCode.FAILSAFE_ACTIVE


def test_guard_requires_paused_mission() -> None:
    context = create_context()
    context.mission_paused = False
    result = CommandGuard().evaluate_vehicle(context)
    assert result.code is GuardCode.MISSION_NOT_PAUSED


def test_guard_requires_multicopter_state() -> None:
    context = create_context()
    context.vtol_state = "FW"
    result = CommandGuard().evaluate_vehicle(context)
    assert result.code is GuardCode.WRONG_VTOL_STATE
