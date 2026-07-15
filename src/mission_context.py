from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MissionContext:
    """비행제어기에서 임무 관리기로 전달되는 통합 상태."""

    connected: bool = False
    health_ok: bool = False
    armed: bool = False
    in_air: bool = False

    altitude_m: float = 0.0
    airspeed_m_s: float = 0.0

    latitude_deg: float = 0.0
    longitude_deg: float = 0.0

    battery_remaining_pct: float = 100.0
    gps_fix: str = "UNKNOWN"
    satellites: int = 0

    flight_mode: str = "UNKNOWN"
    vtol_state: str = "UNDEFINED"

    current_waypoint_name: str = "NONE"
    waypoint_index: int = 0
    waypoint_progress_pct: float = 0.0
    distance_to_waypoint_m: float = 0.0
    navigation_complete: bool = False

    mission_uploaded: bool = False
    mission_started: bool = False
    mission_paused: bool = False
    raw_mission_current: int = 0
    raw_mission_total: int = 0
    raw_mission_progress_pct: float = 0.0
    raw_mission_finished: bool = False

    hover_stable: bool = False
    forward_transition_complete: bool = False

    target_detected: bool = False
    search_complete: bool = False

    back_transition_complete: bool = False
    returned_home: bool = False
    landed: bool = False

    failsafe_triggered: bool = False
    failsafe_code: str = "NONE"
    failsafe_reason: str = ""
    failsafe_action: str = "CONTINUE"
