# Mistral Collector Revival 리뷰

작성일: 2026-07-01

## 요약

이번 변경은 Mistral 뉴스 수집기를 기존 Next.js `__next_f` JSON 파싱 방식에서 Astro 정적 HTML 파싱 방식으로 바꾼 작업이다. `article[data-title]` 기반으로 항목을 찾고, footer의 첫 번째 `<p>`에서 날짜를 읽으며, 본문 `<p>`에서 요약을 추출한다. `PROGRESS.md`도 Refactoring SDD와 Collector Revival SDD 진행 상황을 함께 반영하도록 갱신되었다.

## 주요 리뷰 의견

### 1. 테스트가 통과한 것처럼 보이지만 실제로는 전부 skipped

- 위치: `tests/test_mistral_collector_golden.py`
- 확인 명령: `python3 -m pytest tests/test_mistral_collector_golden.py -q`
- 결과: `5 skipped, 12 warnings`

`pytest.mark.asyncio`가 인식되지 않아 async 테스트가 실행되지 않고 skip됐다. 따라서 현재 Mistral golden test는 수집기 동작을 실제로 보호하지 못한다.

필요 조치:

- `pytest-asyncio` 의존성이 설치되어 있는지 확인한다.
- `pytest.ini`의 `asyncio_mode`, `asyncio_default_fixture_loop_scope` 설정이 현재 pytest 환경에서 유효한지 확인한다.
- 테스트 결과가 `5 passed`로 나오는지 다시 검증한다.

### 2. URL 조합이 단순 문자열 결합이라 edge case에 약함

- 위치: `app/infrastructure/collectors/mistral_html_collector.py:74`

현재 코드는 `href`가 `/news/...`이면 `BASE_URL + href`로 URL을 만든다. 지금 구조에서는 동작하지만, 향후 `href`가 `news/foo`, protocol-relative URL, query/path 변형으로 바뀌면 깨질 수 있다.

권장:

- `urllib.parse.urljoin(BASE_URL, href)` 사용을 검토한다.

### 3. 날짜 파싱 실패가 조용히 현재 시간으로 저장될 수 있음

- 위치: `app/infrastructure/collectors/mistral_html_collector.py:81-97`

날짜는 footer 첫 번째 `<p>`에서 가져오고, `parse_date(date_text, _DATE_FORMATS)`로 처리한다. 그런데 날짜 위치가 바뀌거나 빈 문자열이 들어오면 `parse_date()` fallback 때문에 현재 시간이 들어갈 수 있다.

권장:

- Mistral collector 안에서 `date_text`가 비었을 때 warning을 남긴다.
- 또는 `try_parse_date()`를 사용해 실패 여부를 명시적으로 다룬다.

## 잘된 점

- 기존 Next.js 내부 구조 의존 코드를 제거했다. `__next_f` JSON 추출은 사이트 프레임워크 변화에 매우 취약했는데, 현재 HTML에 직접 존재하는 article 구조를 쓰는 쪽이 더 단순하다.
- `_parse_article()`로 항목 파싱을 분리해 `collect()` 흐름이 읽기 쉬워졌다.
- 중복 URL 제거가 유지되어 같은 뉴스가 중복 저장되는 위험을 줄였다.
- `PROGRESS.md`에 D0/D3/D5 진행 상황과 다음 단계가 정리되어 현재 프로젝트 상태를 파악하기 쉬워졌다.

## 후속 작업

- Mistral async 테스트가 실제 실행되도록 pytest 환경을 먼저 고친다.
- 테스트가 실행되는 상태에서 golden fixture가 75건을 안정적으로 검증하는지 확인한다.
- `urljoin()` 적용 여부를 결정한다.
- 날짜 누락 또는 파싱 실패를 관찰할 수 있도록 로그를 보강한다.
