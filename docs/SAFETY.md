# 안전 지침

## 1. 적용 범위

이 문서는 Pixhawk/PX4, MAVSDK, MissionRaw, Offboard 및 VTOL 명령을 시험할 때 적용한다.

이 프로젝트는 실제 기체의 비행 안전을 인증하지 않는다.

## 2. 절대 원칙

- 첫 실제 연결은 프로펠러 제거 상태에서 수행한다.
- Arm, Takeoff, VTOL Transition, Offboard, Land를 한 번에 시험하지 않는다.
- 기체가 Armed 또는 In-Air 상태이면 임무 저장소 쓰기를 수행하지 않는다.
- 실제 시험 전 QGroundControl에서 기체 상태와 Failsafe 설정을 확인한다.
- 승인되지 않은 장소에서 시험하지 않는다.
- 조종자와 안전관리자를 분리한다.
- 비상 시 즉시 수동 제어 또는 PX4 복구 모드로 전환할 수 있어야 한다.

## 3. 단계별 시험 게이트

### 단계 A: 소프트웨어 전용

- 전체 pytest 통과
- 정상·고장 시나리오 통과
- 로그와 Failure Code 확인

### 단계 B: Arm 없는 실제 FC 연결

- 프로펠러 제거
- 연결 상태 확인
- UID, GPS, 배터리, Arm 상태 읽기
- MissionRaw 다운로드
- 필요 시 Disarmed 지상 상태에서만 업로드·재다운로드 검증

금지:

- Arm
- Takeoff
- Mission Start
- VTOL Transition
- Offboard Start

### 단계 C: 지상 명령 시험

- 프로펠러 제거
- 기체 고정
- 모드 전환과 명령 응답만 검증
- 모터·서보 출력 시험은 별도 절차와 전원 제한 적용

### 단계 D: 실제 비행

다음이 준비되지 않으면 진행하지 않는다.

- 검증된 기체와 파라미터
- RC 조종자
- 안전관리자
- 충분한 시험구역
- 비상 복구 모드
- 통신 손실 대응
- 기상 조건 확인
- 관련 허가와 법령 검토

## 4. Offboard 안전

PX4 Offboard는 외부 Setpoint 스트림이 유지돼야 한다.

필수 조건:

- Offboard 시작 전 초기 Setpoint 전송
- Setpoint 공급 주기 감시
- 데이터가 오래되면 새 명령 차단
- 표적 추정 불안정 시 접근 금지
- 연결·위치추정·Failsafe 상태 확인
- Offboard 종료 실패 시 Hold 또는 RTL
- PX4의 Offboard loss 동작을 사전 설정

## 5. MissionRaw 안전

- 업로드 전에 모든 MissionItem 필드를 검증한다.
- 업로드 후 FC에서 다시 내려받아 원본과 비교한다.
- 불일치가 하나라도 있으면 임무 실행을 차단한다.
- 실제 기체에서 `current`, `autocontinue`, frame, command를 재확인한다.
- 좌표와 고도 기준이 상대고도인지 절대고도인지 확인한다.
- 시험구역 밖 좌표가 없는지 확인한다.

## 6. 로그와 개인정보

GitHub 공개 전에 다음을 제거한다.

- 실제 비행 위치가 포함된 로그
- 개인 주소 또는 민감한 좌표
- 기체 UID
- 시리얼 포트 구성
- 기관 내부 문서
- API 키와 비밀번호
- 실제 사고 영상 또는 개인정보

`.gitignore`는 일반 로그와 비행로그를 기본적으로 제외한다.
