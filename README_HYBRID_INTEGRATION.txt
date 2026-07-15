VTOL Hybrid Mission Integration Patch
기준: 기존 100 passed 프로젝트
목표: 114 passed

추가/변경 기능
1. MissionRaw -> 역천이 -> Offboard 접근 -> 표적 정렬 -> RTL 통합 시뮬레이션
2. 가상 표적 상대 위치 모델 및 NED 속도 명령 반영
3. 역천이 제한시간 감시 및 RTL 복구
4. 추적 손실, 접근 중 Failsafe, 낮은 신뢰도, 역천이 Timeout 시나리오
5. mission_manager.py --hybrid-demo CLI 통합
6. 하이브리드 CSV 로그 저장

적용
압축 해제 후 src, tests 폴더를 프로젝트 루트에 덮어씁니다.

Windows CMD
cd /d C:\dev\vtol-autonomy-lab
call .venv\Scripts\activate.bat
python -m pytest -v

정상 목표
collected 114 items
114 passed

정상 통합 시뮬레이션
python -m src.mission_manager --hybrid-demo --hybrid-scenario normal

고장 주입
python -m src.mission_manager --hybrid-demo --hybrid-scenario low_confidence
python -m src.mission_manager --hybrid-demo --hybrid-scenario tracking_loss
python -m src.mission_manager --hybrid-demo --hybrid-scenario failsafe_during_approach
python -m src.mission_manager --hybrid-demo --hybrid-scenario transition_timeout

정상 출력 핵심
최종 하이브리드 모드: RTL
표적 정렬 완료: True
RTL 복귀 완료: True
안전 완료: True

로그
logs\hybrid\hybrid_normal.csv
