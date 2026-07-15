VTOL Autonomy Lab - MAVSDK MissionRaw Integration Patch

적용 대상:
- 기존 62 passed 상태 프로젝트

추가/변경 파일:
- src/mission_context.py
- src/mavsdk_fc.py
- src/mission_manager.py
- tests/test_mavsdk_mission_integration.py

추가 기능:
1. MavsdkFlightController에 MissionPlan 저장
2. MissionRawUploader 지연 생성 및 연결
3. 임무 업로드/시작/일시정지/삭제 메서드
4. MissionRaw 진행률을 MissionContext에 동기화
5. CSV 텔레메트리에 실제 임무 상태 필드 추가
6. MAVSDK backend 생성 시 MissionPlan 전달

중요 안전사항:
- 이 패치는 임무를 자동으로 시작하지 않습니다.
- upload_mission()은 Arm/이륙/시작 명령을 보내지 않습니다.
- start_uploaded_mission()을 명시적으로 호출할 때만 임무 시작 명령이 전달됩니다.
- 실제 기체 시험 전 프로펠러를 제거하고 QGroundControl에서 기체 상태를 확인하십시오.

테스트:
python -m pytest -v

정상 목표:
72 passed
