# 가상 VTOL 임무 재현·증빙 절차

## 범위
이 절차는 **가상 FC와 Python 테스트만** 검증합니다. MAVSDK/PX4, SITL, 실제 FC 연결·안전성·비행을 검증하지 않습니다. 기본 검증 명령에는 `--backend mavsdk`, `--upload` 또는 실제 기체 제어 옵션을 포함하지 않습니다.

## 환경 및 시작
- Windows PowerShell 또는 Linux/macOS 셸, Python 3.11 권장
- 저장소 루트에서 `python -m venv .venv` 후 활성화
- `python -m pip install -r requirements.txt`
- 버전 및 기준 커밋 기록: `python --version`, `python -m pip freeze`, `git rev-parse HEAD`

## 단일 검증 명령
```sh
python scripts/verify_virtual_mission.py
```

스크립트는 (1) Python 문법 검사, (2) 전체 pytest, (3) `tests/test_failure_scenarios.py`의 시나리오별 최종 상태·실패 코드 단언을 순차 실행합니다. 각 단계가 종료 코드 0을 반환해야 다음 단계로 진행합니다. 기존 정상/저전압 및 고장 시나리오 테스트는 예상 종료 상태와 정확한 실패 코드를 확인합니다. 이는 가상 FC 검증이지 실기체나 PX4 검증이 아닙니다.

## 검토 체크리스트
- [ ] 정상 시나리오의 종료 상태와 실패 코드가 `COMPLETE`, `NONE`인지 확인
- [ ] 저전압 시나리오가 정상 임무 완료로 잘못 표기되지 않는지 확인
- [ ] 실행 실패, 예외, 의존성 문제 없이 각 단계 종료 코드 0 확인
- [ ] 테스트 수와 환경 버전, 커밋 SHA, 날짜, OS 기록
- [ ] 로그를 공개할 때 실제 비행 좌표·장비 키·인증정보 제거
- [ ] 실기체/시뮬레이터/PX4 검증 결과로 재해석하지 않음

## 실패 시
`python -m pytest -x -v`로 최초 실패를 확인하고 `docs/TESTING.md`에 따라 원인을 분리합니다. 필요한 패키지 설치 실패는 *미검증*이지 *시험 통과*가 아닙니다. CI와 로컬에서 같은 커밋으로 재시험하세요.

## 관련 문서
- [테스트](TESTING.md)
- [안전 원칙](SAFETY.md)
- [개발 상태](DEVELOPMENT_STATUS.md)
