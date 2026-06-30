# Retrospect

## Context

이번 변경은 여러 collector에 흩어져 있던 HTTP 요청 처리와 datetime 파싱 로직을 공통 유틸로 모으는 리팩터링이다. 주요 방향은 다음과 같다.

- `app.core.datetime_utils`를 추가해 UTC aware datetime을 일관되게 생성한다.
- `app.infrastructure.http.async_client`를 추가해 collector의 HTTP 요청 설정과 retry 정책을 중앙화한다.
- HTML/API/RSS collector들이 개별 `httpx`, `requests`, `datetime.utcnow()`, `datetime.strptime()` 사용을 줄이고 공통 helper를 사용하도록 바뀌었다.
- `tests/test_core_datetime_utils.py`로 시간 파싱 유틸의 기본 동작을 특성화했다.

## What Went Well

- collector별로 반복되던 `AsyncClient` 설정, timeout, User-Agent, redirect 처리 코드가 `fetch_html()`과 `fetch_json()`으로 모였다. 이후 collector를 추가하거나 정책을 바꿀 때 수정 지점이 줄어든다.
- `datetime.utcnow()`와 naive datetime 생성 경로가 `now_utc()`, `parse_date()`, `parse_struct_time()`로 대체되어 Python 3.12 deprecation과 timezone 혼용 문제를 줄였다.
- `try_parse_date()`를 둔 덕분에 DeepMind/Meta처럼 여러 후보 문자열을 순차적으로 시도한 뒤에만 fallback하는 흐름을 유지할 수 있었다.
- HuggingFace collector가 동기 `requests` + `asyncio.to_thread()` 구조에서 async HTTP helper로 이동해 collector 구현 방식이 다른 수집기들과 더 비슷해졌다.

## Tradeoffs And Risks

- `parse_date()`는 파싱 실패 시 `now_utc()`로 fallback한다. 기존 동작과 비슷하지만, 잘못된 upstream 날짜 형식이 조용히 현재 시각으로 저장될 수 있다. 운영 관점에서는 fallback 발생을 로깅하거나 metric으로 남기는 편이 더 추적 가능하다.
- `fetch_json()`의 타입 힌트는 `dict`지만 HuggingFace collector는 API가 list를 직접 반환할 가능성도 처리한다. helper의 반환 타입을 `Any` 또는 `dict | list`로 넓히는 것이 타입상 더 정확하다.
- 공통 HTTP retry는 모든 `HTTPStatusError`에 재시도한다. 404 같은 영구 실패까지 재시도할 수 있으므로, 필요하면 5xx/429와 transport error 중심으로 좁히는 정책이 더 낫다.
- collector 테스트는 아직 보강되지 않았다. datetime utility는 테스트가 있지만, 각 collector가 새 helper와 파싱 유틸을 올바르게 조합하는지는 별도 fixture 기반 테스트가 필요하다.

## Follow-ups

- `fetch_json()` 반환 타입을 실제 사용 범위에 맞게 조정한다.
- `parse_date()` fallback 발생 시 source와 raw value를 추적할 수 있는 로깅 전략을 검토한다.
- `fetch_html()`/`fetch_json()` retry 정책에 대해 4xx 예외 처리 기준을 정한다.
- 각 collector별 최소 fixture 테스트를 추가해 HTML 구조 변경, 날짜 누락, 중복 URL 처리, tag 추출을 보호한다.
- repository와 scoring 경로에서 timezone-aware datetime이 DB 직렬화/비교 로직과 충돌하지 않는지 통합 테스트로 확인한다.
