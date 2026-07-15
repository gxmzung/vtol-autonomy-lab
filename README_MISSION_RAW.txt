MISSION RAW PATCH
=================

추가 파일
- src/mission_raw_builder.py
- src/mission_raw_uploader.py
- tests/test_mission_raw_builder.py
- tests/test_mission_raw_uploader.py

검증 명령
python -m pytest -v

기대 결과
62 passed

이 단계는 실제 기체를 Arm하거나 이륙시키지 않습니다.
MissionPlan을 MAVLink MISSION_ITEM_INT 형식으로 변환하고,
Fake MissionRaw 플러그인으로 업로드/시작/일시정지/진행률을 검증합니다.
