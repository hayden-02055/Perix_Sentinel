# Scoring & Mistral Wrapup 리뷰

작성일: 2026-07-01

## 요약

이번 변경은 세 가지를 다룬다.

- `scoring_engine._recency_score()`에서 aware/naive datetime 혼합으로 발생하던 subtraction 오류를 방지
- Mistral collector의 URL 생성 로직을 `urljoin()`으로 보강
- `PROGRESS.md`에 Collector Revival 이후 테스트/실가동 결과를 업데이트

## 주요 리뷰 의견

### 1. `PROGRESS.md`의 테스트 결과와 실제 실행 결과가 다름

- 위치: `PROGRESS.md`
- 문서 내용: `42 passed, 0 skipped`, `45 passed`
- 실제 확인 명령: `python3 -m pytest -q`
- 실제 결과: `39 passed, 6 skipped, 14 warnings`

현재 async collector golden test들이 `pytest.mark.asyncio`를 인식하지 못해 실행되지 않고 skip된다. 따라서 `PROGRESS.md`에 적힌 “0 skipped”, “45 passed”는 현재 로컬 환경 기준으로 사실과 맞지 않는다.

필요 조치:

- `pytest-asyncio` 설치 또는 테스트 실행 환경 정비
- `pytest.ini`의 `asyncio_mode`, `asyncio_default_fixture_loop_scope` 설정 유효성 확인
- 실제 결과가 `45 passed, 0 skipped`로 맞춰진 뒤 `PROGRESS.md` 유지

### 2. `_recency_score()`의 timezone 정규화가 non-UTC aware 값에는 부정확할 수 있음

- 위치: `app/domain/services/scoring_engine.py:74-78`

현재 로직은 `now`가 naive이고 `published_at`이 aware이면 `published.replace(tzinfo=None)`로 timezone만 제거한다. production 값이 모두 UTC aware라면 큰 문제는 없지만, offset이 있는 aware datetime이 들어오면 실제 instant 변환 없이 벽시각만 남기므로 recency 계산이 틀어질 수 있다.

예: `2026-07-01 09:00+09:00`은 UTC로 `2026-07-01 00:00Z`인데, `replace(tzinfo=None)`를 하면 `09:00`으로 계산된다.

권장:

- aware 값은 먼저 UTC로 변환한 뒤 naive 비교가 필요할 때만 tzinfo를 제거한다.
- 또는 `_recency_score()` 내부에서 `now`와 `published`를 모두 aware UTC로 통일하는 방식이 더 명확하다.

### 3. mixed datetime 회귀 테스트가 한 방향만 추가됨

- 위치: `tests/test_scoring_characterization.py:132-170`

추가된 테스트는 다음 조합을 확인한다.

- aware now + aware published
- naive now + naive published
- aware now + naive published

하지만 코드에는 `naive now + aware published` 분기도 존재한다. 이 분기가 실제로 안전한지 확인하는 테스트가 없다.

권장:

- `now=NOW`, `published_at=datetime(..., tzinfo=timezone.utc)` 조합 테스트를 추가한다.
- 가능하면 UTC가 아닌 offset timezone 케이스도 하나 추가해 정규화 정책을 고정한다.

## 잘된 점

- `/collect` 실가동 중 발견된 aware/naive subtraction 오류를 scoring layer에서 막도록 회귀 테스트를 추가한 점은 좋다.
- Mistral URL 생성이 `BASE_URL + href`에서 `urljoin(BASE_URL, href)`로 바뀌어 상대 경로 처리 안정성이 좋아졌다.
- `PROGRESS.md`가 단순 작업 목록이 아니라 실제 발견한 버그, 수정 내용, 다음 부채까지 포함하도록 업데이트되었다.

## 검증 결과

- `python3 -m pytest tests/test_scoring_characterization.py -q`
  - 결과: `16 passed, 2 warnings`
- `python3 -m pytest -q`
  - 결과: `39 passed, 6 skipped, 14 warnings`

스코어링 단위 테스트는 통과했지만, 전체 테스트에서는 async collector 테스트가 skip되고 있으므로 테스트 인프라 정리가 먼저 필요하다.
