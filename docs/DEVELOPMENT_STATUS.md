# 개발 상태

## 1. 현재 단계

현재 프로젝트는 다음 단계까지 진행됐다.

```text
정적 임무계획
→ 가상 FC
→ MAVSDK FC 어댑터
→ MissionRaw 생성·업로드
→ FC 저장소 재다운로드·무결성 검증
→ Failsafe·Command Guard
→ MissionRaw–Offboard 하이브리드 제어
→ 가상 표적 접근·정렬·RTL
→ 칼만필터 표적 위치·속도 추정
```

## 2. 구현 현황

| 모듈 | 상태 | 검증 방식 |
|---|---|---|
| MissionContext | 완료 | 단위시험 |
| Mission State Machine | 완료 | 정상·실패 상태시험 |
| Virtual Flight Controller | 완료 | 가상 통합시험 |
| MAVSDK Flight Controller | 구현 | Fake MAVSDK 시험 |
| MissionPlan / Navigator | 완료 | 좌표·진행률 시험 |
| MissionRaw Builder | 완료 | 필드 변환 시험 |
| MissionRaw Uploader | 완료 | Fake 플러그인 시험 |
| MissionRaw Verifier | 완료 | 원본·다운로드 대조 |
| FC Validation CLI | 구현 | Fake FC 및 안전차단 시험 |
| Failsafe Supervisor | 완료 | 고장 주입 |
| Command Guard | 완료 | 허용·거부 조건시험 |
| Offboard Controller | 구현 | Fake Offboard 시험 |
| Hybrid Mission Controller | 통합 시뮬레이션 | 정상·고장 시나리오 |
| Target Kalman Filter | 구현 | 노이즈·이상치·누락시험 |
| 실제 영상 탐지 | 미구현 | 예정 |
| 표적 지상좌표 투영 | 미구현 | 예정 |
| 실제 Pixhawk Offboard | 미검증 | 예정 |
| 정밀착륙 | 미구현 | 예정 |
| 임무장치 | 미구현 | 예정 |

## 3. 검증 수준 구분

### 코드 수준 검증

- 자료구조
- 상태 전환
- 명령 호출 순서
- 고장 대응
- 로그
- MissionRaw 필드 대조
- 표적 필터

### 시뮬레이션 수준 검증

- Virtual FC
- 웨이포인트 경로
- 하이브리드 모드 전환
- 표적 접근과 RTL
- 추적 손실과 Failsafe

### 실제 시스템에서 남은 검증

- 실제 Pixhawk 연결
- 실제 MissionRaw 업로드·재다운로드
- 실제 텔레메트리 스트림
- 실제 VTOL 천이
- 실제 Offboard Setpoint
- 카메라·LiDAR·RTK
- 비행로그 기반 성능분석

## 4. 테스트 상태

README에는 테스트 수가 개발마다 바뀌는 점을 고려해 `100+`로 표시한다.

마지막 직접 확인 기준:

- 기존 통합 프로젝트: 129 passed
- 칼만필터 신규 패치: 16 passed 독립 확인
- 전체 통합 수치: 로컬 `python -m pytest -q` 결과를 기준으로 갱신

## 5. 공개 시 주의

이 저장소를 실제 비행 완료 프로젝트처럼 표현하지 않는다.

권장 표현:

> PX4 VTOL용 상위 자율임무 소프트웨어를 가상 FC와 Fake MAVSDK 환경에서 개발·검증하고 있으며, 실제 FC 검증과 비행실증을 단계적으로 진행할 예정이다.

피해야 할 표현:

> 실제 VTOL 완전자율비행을 완성했다.
