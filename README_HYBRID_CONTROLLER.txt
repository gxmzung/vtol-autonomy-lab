VTOL AUTONOMY LAB - Hybrid Mission Controller Patch
기준 상태: 72 passed
적용 후 목표: 100 passed

추가 기능
1. TargetEstimate: 표적 상대 위치, 신뢰도, 추적 안정성, 시각 관리
2. CommandGuard: MissionRaw -> Offboard 전환 조건 검사
3. OffboardController: NED 속도 명령 생성, 초기 Setpoint, 시작/정지
4. HybridMissionController: MissionRaw 일시정지 -> 역천이 -> Offboard 접근 -> RTL
5. MavsdkFlightController.create_offboard_controller(): 실제 MAVSDK offboard 플러그인 연결

적용
압축 내부 src, tests 폴더를 C:\dev\vtol-autonomy-lab에 덮어쓴다.

검증
cd /d C:\dev\vtol-autonomy-lab
call .venv\Scripts\activate.bat
python -m pytest -v

정상 결과
collected 100 items
100 passed

안전 주의
- 이 패치는 테스트에서 Fake Offboard 플러그인을 사용한다.
- 실제 기체 Arm, 이륙, Mission 시작 명령을 자동으로 실행하지 않는다.
- 실제 Offboard 시험은 프로펠러 제거와 PX4 안전 설정 확인 후 별도 단계에서 진행한다.
