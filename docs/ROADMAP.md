# 로드맵

## Phase 1 — 임무 소프트웨어 기반

- [x] MissionContext
- [x] 상태머신
- [x] 이벤트·텔레메트리 로그
- [x] 정상·실패 시나리오
- [x] Virtual FC
- [x] FlightControllerInterface

## Phase 2 — MAVSDK 및 임무 저장소

- [x] MavsdkFlightController
- [x] MissionPlan
- [x] MissionRawBuilder
- [x] MissionRawUploader
- [x] Mission progress
- [x] MissionRawVerifier
- [x] Arm 없는 FC 검증 CLI

## Phase 3 — 안전과 하이브리드 제어

- [x] Failsafe Supervisor
- [x] Command Guard
- [x] Offboard Controller
- [x] Hybrid Mission Controller
- [x] MissionRaw → Offboard → RTL 통합 시뮬레이션
- [x] 추적 손실·천이 실패·Failsafe 복구

## Phase 4 — 표적 상태추정

- [x] TargetMeasurement
- [x] 2D Constant-Velocity Kalman Filter
- [x] 이상치 제거
- [x] 짧은 탐지 누락 예측
- [x] 공분산 기반 안정성 판정
- [ ] HybridMissionController와 필터 출력 직접 연결
- [ ] 노이즈 수준별 접근 성능 분석
- [ ] 필터 결과 시각화

## Phase 5 — 비전 및 좌표추정

- [ ] 카메라 입력 계층
- [ ] 객체 탐지 어댑터
- [ ] 다중 프레임 표적 추적
- [ ] 카메라 내부 파라미터
- [ ] 기체 자세·짐벌 자세 융합
- [ ] 영상 좌표 → 지상 좌표 변환
- [ ] 표적 좌표 신뢰도 모델

## Phase 6 — 실제 PX4 검증

- [ ] Pixhawk UID·텔레메트리 읽기
- [ ] MissionRaw 업로드·재다운로드 검증
- [ ] QGroundControl 임무 대조
- [ ] 프로펠러 제거 Offboard 명령시험
- [ ] PX4 Offboard loss 복구 검증
- [ ] VTOL 천이 상태 수신 검증
- [ ] 로그 동기화

## Phase 7 — 실제 임무

- [ ] 제한된 비행구역 웨이포인트 시험
- [ ] MissionRaw–Offboard 전환 비행
- [ ] 표적 접근·정렬
- [ ] 정밀착륙
- [ ] 임무장치 인터페이스
- [ ] 반복 실증과 성능지표

## 성능지표 후보

- 임무 성공률
- 웨이포인트 도달 오차
- 표적 추정 RMSE
- 이상치 거부율
- 탐지 누락 허용시간
- Offboard 접근시간
- 목표 정렬 오차
- 천이 중 고도 손실
- Failsafe 감지·복구시간
