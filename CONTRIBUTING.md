# 기여 안내

## 개발 원칙

- 안전 관련 기본값은 보수적으로 설정한다.
- 실제 FC 명령과 Fake 객체를 분리한다.
- 새로운 기능에는 정상·실패 테스트를 함께 추가한다.
- 상태 전환은 암묵적으로 처리하지 않고 상태머신에 명시한다.
- 예외를 숨기지 않고 Failure Code 또는 로그로 남긴다.
- 실제 기체 자동 Arm·이륙 기능을 기본 활성화하지 않는다.

## 개발 환경

```cmd
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
python -m pytest -v
```

## 브랜치 이름

```text
feature/mission-replan
fix/offboard-timeout
test/target-outlier
docs/architecture-update
```

## 커밋 예시

```text
feat: add filtered target pipeline
fix: reject stale offboard target
test: cover mission pause failure
docs: update FC validation procedure
```

## Pull Request 조건

- 전체 테스트 통과
- 변경 목적 설명
- 안전 영향 설명
- 새 CLI 옵션 문서화
- 실제 FC 명령 추가 시 기본 비활성화
- 로그나 설정 파일에 민감한 좌표가 없는지 확인

## 코드 스타일

- Python 3.11 타입힌트 사용
- 공개 함수·클래스에 docstring 작성
- 긴 함수는 판단·명령·로그 계층으로 분리
- 파일 간 순환 import 금지
- 상수와 임계값을 설정 객체로 이동
