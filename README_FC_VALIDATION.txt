VTOL Autonomy Lab - Safe FC Validation Patch

적용 대상:
- 기존 72 passed 상태 프로젝트

검증 완료:
- Python 자동시험 87 passed
- MAVSDK-Python 3.15.3 환경에서 87 passed

추가/변경 파일:
- src/mission_raw_uploader.py
- src/mavsdk_fc.py
- src/mission_raw_verifier.py
- src/fc_validator.py
- src/fc_validation_cli.py
- tests/test_mission_raw_verifier.py
- tests/test_fc_validator.py
- tests/test_fc_validation_cli.py

추가 기능:
1. MissionRaw download_mission() 읽기
2. 업로드 원본과 다운로드 항목 자동 대조
3. 항목 수, seq, frame, command, current, autocontinue 비교
4. 위도/경도 정수 좌표, 상대고도, 도달 반경, hold time 비교
5. 기체 Hardware UID / Legacy UID 조회
6. Arm 및 비행 상태 안전 인터록
7. JSON/CSV 검증 보고서 저장
8. 안전 전용 CLI

안전 정책:
- ARM 명령 없음
- TAKEOFF 명령 없음
- START MISSION 명령 없음
- VTOL TRANSITION 명령 없음
- 기체가 Armed 또는 In Air이면 업로드/다운로드 대조 중단
- 실제 Pixhawk 시험은 프로펠러 제거 상태에서 진행

테스트:
python -m pytest -v

정상 목표:
87 passed

연결 상태만 확인하고 현재 저장 임무를 다운로드 대조:
python -m src.fc_validation_cli ^
  --connection-url serial://COM5:57600 ^
  --mission-file config\mission.json

안전 인터록 통과 후 임무 저장 + 재다운로드 대조:
python -m src.fc_validation_cli ^
  --connection-url serial://COM5:57600 ^
  --mission-file config\mission.json ^
  --upload

UDP/SITL 연결 예시:
python -m src.fc_validation_cli ^
  --connection-url udpin://0.0.0.0:14540 ^
  --mission-file config\mission.json ^
  --upload

주의:
- COM 포트와 baud rate는 장치 관리자 및 Pixhawk 연결 방식에 맞게 변경하십시오.
- --upload는 기존 임무를 기본적으로 삭제한 뒤 새 임무를 저장합니다.
- 기존 임무를 삭제하지 않으려면 --keep-existing를 추가하십시오.
- 검증 보고서는 logs\fc_validation 폴더에 JSON과 CSV로 생성됩니다.
