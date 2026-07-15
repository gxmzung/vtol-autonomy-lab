# 변경 이력

이 프로젝트는 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 형식을 참고한다.

## [Unreleased]

### Added

- 컴패니언 컴퓨터 중심의 VTOL 임무관리 아키텍처
- 상태머신 및 통합 MissionContext
- Virtual Flight Controller
- MAVSDK Flight Controller 어댑터
- JSON MissionPlan 및 좌표 기반 Waypoint Navigator
- MissionRaw Builder, Uploader, Verifier
- FC 저장소 업로드·재다운로드 안전 검증 CLI
- 텔레메트리·상태 전환 CSV 로그
- Failsafe Supervisor
- Command Guard
- Offboard Controller
- Hybrid Mission Controller
- MissionRaw → Offboard → RTL 통합 시뮬레이션
- 저전압, GPS 손실, 링크 손실, 고도·속도 제한 고장 주입
- 2D 등속도 칼만필터 기반 표적 위치·속도 추정
- 표적 측정 노이즈·누락·이상치 시뮬레이터
- 공분산·신뢰도·데이터 수명 기반 Offboard 접근 게이트
- GitHub 문서, 안전 지침, CI, 이슈 템플릿

### Safety

- Armed 또는 In-Air 상태에서 검증 CLI 임무 쓰기 차단
- 실제 FC 검증에서 Arm·Takeoff·Mission Start·VTOL Transition 제외
- Offboard 진입 전 초기 Setpoint와 안전조건 검사
- 추적 손실 또는 Failsafe 시 RTL 복구 경로
