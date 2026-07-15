# GitHub 공개 체크리스트

## 1. 공개 전 정리

- [ ] 전체 테스트 실행
- [ ] 실제 테스트 통과 수 확인
- [ ] `README.md` 실행 명령이 현재 코드와 일치하는지 확인
- [ ] `config/mission.json`에 민감한 실제 좌표가 없는지 확인
- [ ] `logs/`에서 실제 위치·UID·사고자료 제거
- [ ] 기관 내부 PDF와 팀 내부 문서 제거
- [ ] 이메일·전화번호·개인정보 제거
- [ ] API 키, 토큰, 비밀번호 제거
- [ ] 대용량 영상과 비행로그 제거
- [ ] MIT 라이선스의 저작권자 표기 확인

## 2. 권장 저장소 설명

```text
Companion-computer autonomy framework for PX4 VTOL using MissionRaw, MAVSDK Offboard, failsafe supervision, virtual flight control and target state estimation.
```

## 3. 권장 Topics

```text
px4
mavsdk
mavlink
vtol
uav
drone
autonomous-flight
offboard-control
mission-planning
kalman-filter
flight-control
python
```

## 4. Git 초기화

```cmd
cd /d C:\dev\vtol-autonomy-lab
git init
git add .
git commit -m "feat: publish VTOL autonomy framework"
git branch -M main
```

## 5. 원격 저장소 연결

새 원격 저장소인 경우:

```cmd
git remote add origin https://github.com/gxmzung/vtol-autonomy-lab.git
git push -u origin main
```

이미 `origin`이 있는 경우:

```cmd
git remote set-url origin https://github.com/gxmzung/vtol-autonomy-lab.git
git push -u origin main
```

## 6. 첫 릴리스 전

- [ ] 버전 결정: `v0.1.0`
- [ ] `CHANGELOG.md` 갱신
- [ ] 테스트 결과 캡처
- [ ] 실제 비행 미검증 범위를 Release Notes에 명시
- [ ] Git tag 생성

```cmd
git tag -a v0.1.0 -m "Initial public research release"
git push origin v0.1.0
```

## 7. 첫 Release Notes 예시

```markdown
## VTOL Autonomy Lab v0.1.0

Initial research release of a companion-computer autonomy framework for PX4 VTOL.

### Included
- Mission state machine and Virtual FC
- MAVSDK flight-controller adapter
- MissionRaw build, upload and verification layer
- Failsafe Supervisor and Command Guard
- Hybrid MissionRaw–Offboard control simulation
- 2D Kalman-filter target state estimation
- Automated failure-injection tests

### Validation scope
The current release focuses on software, fake-MAVSDK and virtual-flight validation. It does not claim completed real-aircraft flight validation.
```
