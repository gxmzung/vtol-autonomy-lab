from src.filtered_target_pipeline import (
    FilteredTargetPipeline,
)
from src.target_filter import (
    TargetFilterConfig,
    TargetMeasurement,
)


def test_pipeline_blocks_uninitialized_target() -> None:
    pipeline = FilteredTargetPipeline()

    estimate = pipeline.process(
        now_s=0.0,
        measurement=None,
    )
    gate = pipeline.check_offboard_target(
        estimate
    )

    assert gate.allowed is False


def test_pipeline_allows_stable_filtered_target() -> None:
    config = TargetFilterConfig(
        measurement_std_m=0.2,
        stable_position_std_m=3.0,
        stable_after_accepted_count=3,
    )
    pipeline = FilteredTargetPipeline(
        config=config,
        minimum_output_confidence=0.2,
    )

    estimate = None

    for timestamp_s in (0.0, 1.0, 2.0):
        estimate = pipeline.process(
            now_s=timestamp_s,
            measurement=TargetMeasurement(
                timestamp_s=timestamp_s,
                north_m=10.0,
                east_m=-2.0,
                confidence=0.95,
            ),
        )

    assert estimate is not None

    gate = pipeline.check_offboard_target(
        estimate
    )

    assert gate.allowed is True
