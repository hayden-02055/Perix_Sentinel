# Hacker News Collector 리뷰

작성일: 2026-07-01

## 요약

이번 변경은 Hacker News Firebase API 기반 컬렉터를 추가하고 `/collect` 실행 대상에 `"hackernews": HackerNewsApiCollector()`를 등록하는 작업이다. HN `time` 필드를 처리하기 위해 `datetime_utils.from_epoch()`도 추가되었고, 관련 단위 테스트가 보강되었다.

## 주요 리뷰 의견

### 1. `PROGRESS.md`의 `49 passed` 기록이 현재 환경에서 재현되지 않음

- 위치: `PROGRESS.md`
- 문서 내용: `49 passed`
- 실제 확인 명령: `python3 -m pytest -q`
- 실제 결과: arXiv 테스트가 `ModuleNotFoundError: No module named 'feedparser'`로 collection 단계에서 중단

현재 전체 테스트는 HN 변경까지 도달하기 전에 arXiv 테스트 import error로 실패한다. 따라서 `PROGRESS.md`의 “49 passed”는 현재 repo 실행 환경 기준으로 재현되지 않는다.

필요 조치:

- 현재 Python 환경에 `requirements.txt`가 설치되어 있는지 확인한다.
- `feedparser`, `pytest-asyncio`가 실제 테스트 런타임에서 import 가능한지 확인한다.
- 환경 정리 후 `python3 -m pytest -q` 결과를 문서와 맞춘다.

### 2. HN 골든 테스트가 실제 실행되지 않고 skipped 됨

- 위치: `tests/test_hackernews_collector_golden.py`
- 확인 명령: `python3 -m pytest tests/test_hackernews_collector_golden.py -q`
- 실제 결과: `1 skipped, 4 warnings`

`pytest.mark.asyncio`가 현재 환경에서 인식되지 않아 async 테스트가 실행되지 않는다. 즉 HN golden fixture는 아직 컬렉터 동작을 보호하지 못한다.

필요 조치:

- `pytest-asyncio` 설치 및 pytest 설정을 현재 버전에 맞게 정리한다.
- HN 테스트가 `1 passed`로 실행되는지 확인한다.

### 3. HN item fetch 실패가 조용히 부분 성공으로 처리됨

- 위치: `app/infrastructure/collectors/hackernews_api_collector.py:61-69`

개별 item fetch 실패는 warning 후 `None`으로 처리되어 전체 수집은 계속된다. 운영 안정성 측면에서는 합리적이지만, topstories 100개 중 상당수가 실패해도 최종 결과만 보면 “AI 관련 항목이 적었다”와 “API fetch가 많이 실패했다”를 구분하기 어렵다.

권장:

- 실패 개수를 집계해 마지막 로그에 함께 남긴다.
- 실패율이 일정 기준을 넘으면 warning 레벨을 높이거나 collector 결과 메타데이터로 드러낸다.

### 4. `fetch_json()` 반환 타입과 실제 사용이 계속 어긋남

- 위치: `app/infrastructure/collectors/hackernews_api_collector.py:56`

HN `topstories.json`은 list를 반환하지만 공통 helper `fetch_json()`은 타입상 `dict`로 선언되어 있다. 이전 HuggingFace/arXiv에서도 비슷한 패턴이 있었고, HN 추가로 mismatch가 더 명확해졌다.

권장:

- `fetch_json()` 반환 타입을 `Any` 또는 `dict | list`로 조정한다.
- collector 쪽에서 예상 타입을 검사해 API 계약이 깨졌을 때 명확히 실패하도록 한다.

## 잘된 점

- HN API를 scraping 없이 공식 Firebase API로 붙인 점은 유지보수 리스크가 낮다.
- `from_epoch()`를 공통 datetime 유틸로 추가해 epoch 변환 로직을 collector 내부에 흩뿌리지 않았다.
- URL 없는 self-post를 HN discussion URL로 fallback하는 처리는 중복 판정과 사용자 접근성 측면에서 적절하다.
- `Semaphore(10)`으로 item 상세 호출 동시성을 제한한 점은 API 매너 측면에서 좋다.
- metadata에 `score`, `descendants`, `by`, `hn_id`, `type`을 보존해 향후 popularity scoring 설계 재료를 남겼다.

## 검증 결과

- `python3 -m pytest tests/test_core_datetime_utils.py -q`
  - 결과: `25 passed, 2 warnings`
- `python3 -m pytest tests/test_hackernews_collector_golden.py -q`
  - 결과: `1 skipped, 4 warnings`
- `python3 -m pytest -q`
  - 결과: arXiv 테스트 `feedparser` import error로 중단

현재 기준으로 `from_epoch()` 테스트는 통과했지만, HN collector 테스트와 전체 테스트 통과는 확인되지 않았다.
