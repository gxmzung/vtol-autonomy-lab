from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True, slots=True)
class Waypoint:
    name: str
    latitude_deg: float
    longitude_deg: float
    relative_altitude_m: float
    acceptance_radius_m: float = 5.0
    fly_through: bool = True

    def __post_init__(self) -> None:
        waypoint_name = self.name.strip()
        if not waypoint_name:
            raise ValueError("웨이포인트 이름은 비어 있을 수 없습니다.")
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError("위도는 -90도 이상 90도 이하여야 합니다.")
        if not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError("경도는 -180도 이상 180도 이하여야 합니다.")
        if self.relative_altitude_m < 0.0:
            raise ValueError("상대고도는 0 이상이어야 합니다.")
        if self.acceptance_radius_m <= 0.0:
            raise ValueError("도달 반경은 0보다 커야 합니다.")
        object.__setattr__(self, "name", waypoint_name)


@dataclass(frozen=True, slots=True)
class MissionPlan:
    name: str
    waypoints: tuple[Waypoint, ...]

    def __post_init__(self) -> None:
        mission_name = self.name.strip()
        if not mission_name:
            raise ValueError("임무 이름은 비어 있을 수 없습니다.")
        if len(self.waypoints) < 2:
            raise ValueError("임무에는 최소 2개의 웨이포인트가 필요합니다.")
        waypoint_names = [waypoint.name for waypoint in self.waypoints]
        if len(waypoint_names) != len(set(waypoint_names)):
            raise ValueError("웨이포인트 이름은 중복될 수 없습니다.")
        object.__setattr__(self, "name", mission_name)

    @classmethod
    def from_iterable(cls, name: str, waypoints: Iterable[Waypoint]) -> MissionPlan:
        return cls(name=name, waypoints=tuple(waypoints))

    @property
    def total_waypoints(self) -> int:
        return len(self.waypoints)


@dataclass(frozen=True, slots=True)
class NavigationUpdate:
    current_index: int
    current_waypoint_name: str
    distance_to_waypoint_m: float
    waypoint_reached: bool
    advanced: bool
    mission_completed: bool
    progress_pct: float


def haversine_distance_m(
    latitude_a_deg: float,
    longitude_a_deg: float,
    latitude_b_deg: float,
    longitude_b_deg: float,
) -> float:
    latitude_a_rad = math.radians(latitude_a_deg)
    longitude_a_rad = math.radians(longitude_a_deg)
    latitude_b_rad = math.radians(latitude_b_deg)
    longitude_b_rad = math.radians(longitude_b_deg)
    delta_latitude = latitude_b_rad - latitude_a_rad
    delta_longitude = longitude_b_rad - longitude_a_rad
    haversine_value = (
        math.sin(delta_latitude / 2.0) ** 2
        + math.cos(latitude_a_rad)
        * math.cos(latitude_b_rad)
        * math.sin(delta_longitude / 2.0) ** 2
    )
    haversine_value = min(1.0, max(0.0, haversine_value))
    central_angle = 2.0 * math.asin(math.sqrt(haversine_value))
    return EARTH_RADIUS_M * central_angle


class WaypointNavigator:
    def __init__(self, mission_plan: MissionPlan) -> None:
        self.mission_plan = mission_plan
        self.current_index = 0
        self.completed = False
        self.reached_waypoint_names: list[str] = []

    @property
    def current_waypoint(self) -> Waypoint:
        if self.completed:
            return self.mission_plan.waypoints[-1]
        return self.mission_plan.waypoints[self.current_index]

    @property
    def progress_pct(self) -> float:
        completed_count = len(self.reached_waypoint_names)
        return min(
            100.0,
            (completed_count / self.mission_plan.total_waypoints) * 100.0,
        )

    def update_position(self, latitude_deg: float, longitude_deg: float) -> NavigationUpdate:
        if self.completed:
            final_waypoint = self.mission_plan.waypoints[-1]
            return NavigationUpdate(
                current_index=self.current_index,
                current_waypoint_name=final_waypoint.name,
                distance_to_waypoint_m=0.0,
                waypoint_reached=True,
                advanced=False,
                mission_completed=True,
                progress_pct=100.0,
            )

        waypoint = self.current_waypoint
        distance_m = haversine_distance_m(
            latitude_a_deg=latitude_deg,
            longitude_a_deg=longitude_deg,
            latitude_b_deg=waypoint.latitude_deg,
            longitude_b_deg=waypoint.longitude_deg,
        )
        waypoint_reached = distance_m <= waypoint.acceptance_radius_m
        advanced = False

        if waypoint_reached:
            if waypoint.name not in self.reached_waypoint_names:
                self.reached_waypoint_names.append(waypoint.name)
            if self.current_index >= self.mission_plan.total_waypoints - 1:
                self.completed = True
            else:
                self.current_index += 1
                advanced = True

        return NavigationUpdate(
            current_index=self.current_index,
            current_waypoint_name=waypoint.name,
            distance_to_waypoint_m=distance_m,
            waypoint_reached=waypoint_reached,
            advanced=advanced,
            mission_completed=self.completed,
            progress_pct=self.progress_pct,
        )


def waypoint_from_dict(data: dict[str, Any]) -> Waypoint:
    try:
        return Waypoint(
            name=str(data["name"]),
            latitude_deg=float(data["latitude_deg"]),
            longitude_deg=float(data["longitude_deg"]),
            relative_altitude_m=float(data["relative_altitude_m"]),
            acceptance_radius_m=float(data.get("acceptance_radius_m", 5.0)),
            fly_through=bool(data.get("fly_through", True)),
        )
    except KeyError as error:
        raise ValueError(f"필수 웨이포인트 항목이 없습니다: {error.args[0]}") from error


def load_mission_plan(path: str | Path) -> MissionPlan:
    mission_path = Path(path)
    if not mission_path.exists():
        raise FileNotFoundError(f"임무 파일을 찾을 수 없습니다: {mission_path}")
    try:
        with mission_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError("임무 JSON 형식이 올바르지 않습니다.") from error
    if not isinstance(data, dict):
        raise ValueError("임무 JSON 최상위 값은 객체여야 합니다.")
    raw_waypoints = data.get("waypoints")
    if not isinstance(raw_waypoints, list):
        raise ValueError("waypoints 항목은 배열이어야 합니다.")
    waypoints = tuple(waypoint_from_dict(item) for item in raw_waypoints)
    return MissionPlan(
        name=str(data.get("name", "unnamed_mission")),
        waypoints=waypoints,
    )
