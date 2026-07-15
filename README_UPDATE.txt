VTOL Autonomy Lab - Failsafe Supervisor 업데이트

1. 압축을 C:\dev\vtol-autonomy-lab 에 덮어쓰기합니다.
2. CMD에서 실행:

cd /d C:\dev\vtol-autonomy-lab
call .venv\Scripts\activate.bat
python -m pytest -v

정상 목표: 48 passed

정상 임무:
python -m src.mission_manager --backend virtual --scenario normal --mission-file config\mission.json

고장 주입 시험:
python -m src.mission_manager --backend virtual --scenario low_battery
python -m src.mission_manager --backend virtual --scenario gps_loss
python -m src.mission_manager --backend virtual --scenario altitude_limit
python -m src.mission_manager --backend virtual --scenario airspeed_limit

예상 실패 코드:
LOW_BATTERY
GPS_LOST
ALTITUDE_LIMIT_EXCEEDED
AIRSPEED_LIMIT_EXCEEDED
