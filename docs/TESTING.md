# 테스트 가이드

## 1. 전체 테스트

```cmd
cd /d C:\dev\vtol-autonomy-lab
call .venv\Scripts\activate.bat
python -m pytest -v
```

빠른 실행:

```cmd
python -m pytest -q
```

테스트 수집:

```cmd
python -m pytest --collect-only -q
```

## 2. 영역별 실행

상태머신:

```cmd
python -m pytest tests\test_state_machine.py -v
```

고장 시나리오:

```cmd
python -m pytest tests\test_failure_scenarios.py -v
```

MissionRaw:

```cmd
python -m pytest tests\test_mission_raw_builder.py -v
python -m pytest tests\test_mission_raw_uploader.py -v
```

MAVSDK 어댑터:

```cmd
python -m pytest tests\test_mavsdk_fc.py -v
```

하이브리드 제어:

```cmd
python -m pytest tests\test_hybrid_mission_controller.py -v
python -m pytest tests\test_offboard_controller.py -v
python -m pytest tests\test_command_guard.py -v
```

표적 필터:

```cmd
python -m pytest tests\test_target_filter.py -v
python -m pytest tests\test_noisy_target_simulator.py -v
python -m pytest tests\test_filtered_target_pipeline.py -v
```

## 3. 테스트 범위

| 영역 | 주요 검증 |
|---|---|
| MissionContext | 기본 상태와 자료형 |
| State Machine | 정상 전환, 타임아웃, Abort |
| Virtual FC | 연결, Arm 조건, 이륙, 천이, 귀환, 착륙 |
| MAVSDK FC | Fake SDK 연결, 명령 호출, 텔레메트리 |
| MissionPlan | 좌표·고도·중복·JSON 검증 |
| Waypoint Navigator | 거리, 도달 반경, 진행률 |
| MissionRaw Builder | seq, frame, command, x/y/z, param |
| MissionRaw Uploader | 업로드, 시작, 일시정지, 진행률 |
| MissionRaw Verifier | 업로드·다운로드 항목 대조 |
| Failsafe | 배터리, GPS, 링크, 고도, 속도 |
| Hybrid Controller | MissionRaw → Offboard → RTL |
| Target Filter | 위치·속도, 이상치, 누락, stale |
| CLI | 안전 차단, 보고서 생성 |

## 4. 대표 고장 주입

- `takeoff_stall`
- `transition_timeout`
- `link_loss`
- `low_battery`
- `gps_loss`
- `altitude_limit`
- `airspeed_limit`
- `low_confidence`
- `tracking_loss`
- `failsafe_during_approach`

각 시나리오는 예상 최종 상태와 Failure Code를 검증해야 한다.

## 5. 테스트 통과 수 표기 원칙

README에는 변동이 잦은 정확한 숫자 대신 `100+ automated tests`를 사용한다.

릴리스 또는 발표 문서에 정확한 숫자를 쓸 때는 반드시 로컬에서 다음 명령을 실행한 결과를 기준으로 한다.

```cmd
python -m pytest -q
```

대화에서 마지막으로 직접 확인된 기준은 129 passed였으며, 이후 칼만필터 패치의 신규 16개 테스트가 독립적으로 통과했다. 저장소 전체 통합 수치는 로컬 전체 실행 결과를 우선한다.

## 6. 실패 시 확인 순서

1. 현재 가상환경 Python 경로 확인

```cmd
where python
python --version
```

2. 프로젝트 루트 확인

```cmd
cd
dir src
dir tests
```

3. 문법 검사

```cmd
python -m compileall src tests
```

4. 첫 실패만 확인

```cmd
python -m pytest -x -v
```

5. ImportError 발생 시 파일 내부의 잘못된 붙여넣기와 순환 import를 확인한다.

## 7. 실제 FC 시험과 자동시험의 차이

Fake MAVSDK 테스트는 API 호출 순서와 내부 판단을 검증한다. 다음 항목을 증명하지는 않는다.

- 실제 시리얼·UDP 연결 안정성
- 실제 PX4 펌웨어와 플러그인 호환성
- 센서 정확도
- VTOL 기체 파라미터
- 실제 공력·진동·통신 지연
- 실제 Offboard Failsafe 설정

따라서 자동시험 통과는 실제 비행 허가가 아니라 다음 시험 단계로 이동하기 위한 조건이다.
