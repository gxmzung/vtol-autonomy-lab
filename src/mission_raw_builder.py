from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.mission_plan import MissionPlan, Waypoint


MAV_FRAME_GLOBAL_RELATIVE_ALT_INT = 6
MAV_CMD_NAV_WAYPOINT = 16
MAV_MISSION_TYPE_MISSION = 0
COORDINATE_SCALE = 10_000_000


@dataclass(frozen=True, slots=True)
class RawMissionItemData:
    """MAVLink MISSION_ITEM_INT와 1:1로 대응하는 플랫폼 독립 데이터."""

    seq: int
    frame: int
    command: int
    current: int
    autocontinue: int
    param1: float
    param2: float
    param3: float
    param4: float
    x: int
    y: int
    z: float
    mission_type: int

    def __post_init__(self) -> None:
        if self.seq < 0:
            raise ValueError("임무 순번은 0 이상이어야 합니다.")
        if self.current not in {0, 1}:
            raise ValueError("current 값은 0 또는 1이어야 합니다.")
        if self.autocontinue not in {0, 1}:
            raise ValueError("autocontinue 값은 0 또는 1이어야 합니다.")
        if self.z < 0.0:
            raise ValueError("상대고도는 0 이상이어야 합니다.")

    def to_mavsdk_item(
        self,
        item_factory: Callable[..., Any] | None = None,
    ) -> Any:
        """MAVSDK MissionItem 객체로 변환한다.

        테스트에서는 item_factory를 주입하고, 실제 실행에서는
        mavsdk.mission_raw.MissionItem을 지연 import한다.
        """

        if item_factory is None:
            try:
                from mavsdk.mission_raw import MissionItem
            except ImportError as error:
                raise RuntimeError(
                    "MAVSDK가 설치되지 않아 MissionRaw 항목을 만들 수 없습니다."
                ) from error

            item_factory = MissionItem

        return item_factory(
            self.seq,
            self.frame,
            self.command,
            self.current,
            self.autocontinue,
            self.param1,
            self.param2,
            self.param3,
            self.param4,
            self.x,
            self.y,
            self.z,
            self.mission_type,
        )


def encode_coordinate_deg(value_deg: float) -> int:
    """위도·경도를 MISSION_ITEM_INT 정수 좌표로 변환한다."""

    if not math.isfinite(value_deg):
        raise ValueError("좌표는 유한한 숫자여야 합니다.")

    return int(round(value_deg * COORDINATE_SCALE))


def build_raw_waypoint_item(
    waypoint: Waypoint,
    seq: int,
    is_current: bool,
    stop_hold_time_s: float = 1.0,
) -> RawMissionItemData:
    """하나의 Waypoint를 MAV_CMD_NAV_WAYPOINT 항목으로 변환한다."""

    if seq < 0:
        raise ValueError("임무 순번은 0 이상이어야 합니다.")
    if stop_hold_time_s < 0.0:
        raise ValueError("정지 유지시간은 0 이상이어야 합니다.")

    hold_time_s = 0.0 if waypoint.fly_through else stop_hold_time_s

    return RawMissionItemData(
        seq=seq,
        frame=MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        command=MAV_CMD_NAV_WAYPOINT,
        current=1 if is_current else 0,
        autocontinue=1,
        param1=hold_time_s,
        param2=waypoint.acceptance_radius_m,
        # 0은 경로점을 통과하는 기본 경로를 의미한다.
        param3=0.0,
        # NaN은 비행제어기의 기본 yaw 정책을 사용한다.
        param4=float("nan"),
        x=encode_coordinate_deg(waypoint.latitude_deg),
        y=encode_coordinate_deg(waypoint.longitude_deg),
        z=waypoint.relative_altitude_m,
        mission_type=MAV_MISSION_TYPE_MISSION,
    )


def build_raw_mission_items(
    mission_plan: MissionPlan,
    stop_hold_time_s: float = 1.0,
) -> tuple[RawMissionItemData, ...]:
    """MissionPlan 전체를 순서가 보장된 MissionRaw 항목으로 변환한다."""

    if mission_plan.total_waypoints < 2:
        raise ValueError("MissionRaw 임무에는 최소 2개 경로점이 필요합니다.")

    return tuple(
        build_raw_waypoint_item(
            waypoint=waypoint,
            seq=index,
            is_current=index == 0,
            stop_hold_time_s=stop_hold_time_s,
        )
        for index, waypoint in enumerate(mission_plan.waypoints)
    )


def build_mavsdk_mission_items(
    mission_plan: MissionPlan,
    item_factory: Callable[..., Any] | None = None,
    stop_hold_time_s: float = 1.0,
) -> list[Any]:
    """MissionPlan을 MAVSDK upload_mission()에 전달할 객체 목록으로 변환한다."""

    return [
        item.to_mavsdk_item(item_factory=item_factory)
        for item in build_raw_mission_items(
            mission_plan=mission_plan,
            stop_hold_time_s=stop_hold_time_s,
        )
    ]
