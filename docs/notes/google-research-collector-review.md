# Google Research Collector 리뷰

작성일: 2026-07-01

## 요약

이번 변경은 Google Research RSS 컬렉터를 추가하고 `/collect` 실행 대상에 `"google_research": GoogleResearchRssCollector()`를 등록하는 작업이다. `source="Google Research"`로 DeepMind와 분리하고, RSS tag/category와 제목 키워드를 이용해 AI 관련 글만 통과시키는 필터가 들어갔다.

## 주요 리뷰 의견

### 1. 현재 환경에서는 Google Research 테스트와 전체 테스트가 실행되지 않음

- 위치: `tests/test_google_research_collector_golden.py`
- 확인 명령: `python3 -m pytest tests/test_google_research_collector_golden.py -q`
- 실제 결과: `ModuleNotFoundError: No module named 'feedparser'`

`GoogleResearchRssCollector`는 import 시점에 `feedparser`가 필요하다. 현재 Python 환경에는 `feedparser`가 없어 Google Research 테스트가 collection 단계에서 실패한다. 같은 환경에서 앱을 실행하면 `/collect` 라우터 import도 깨질 수 있다.

필요 조치:

- 현재 실행 환경에 `requirements.txt`가 실제로 설치되어 있는지 확인한다.
- `feedparser` 설치 후 Google Research 테스트를 다시 실행한다.
- 앱 실행 환경과 테스트 환경의 dependency set을 맞춘다.

### 2. `PROGRESS.md`의 `52 passed` 기록이 현재 repo 상태로 재현되지 않음

- 위치: `PROGRESS.md`
- 문서 내용: `52 passed`
- 실제 확인 명령: `python3 -m pytest -q`
- 실제 결과: arXiv/Google Research/NVIDIA 테스트가 모두 `feedparser` import error로 중단

문서에는 전체 회귀가 통과한 것으로 기록되어 있지만, 현재 환경 기준으로는 테스트가 시작 단계에서 실패한다.

권장:

- 실제 통과한 환경과 명령을 명시한다.
- 현재 repo 환경에서 재현 가능하게 의존성을 정리한 뒤 passed count를 유지한다.

### 3. tag/category 파싱이 필드 누락에 약함

- 위치: `app/infrastructure/collectors/google_research_rss_collector.py:36-37`, `63-65`

현재 코드는 `t["term"].lower()`로 직접 접근한다. feedparser가 예상과 다른 tag object를 반환하거나 일부 tag에 `term`이 없으면 한 entry 때문에 수집 전체가 `KeyError`로 중단될 수 있다.

권장:

- `term = t.get("term")` 형태로 방어적으로 처리한다.
- 빈 term은 제외한다.
- `_is_ai_related()`와 tags 생성 로직에서 같은 helper를 재사용해 중복을 줄인다.

### 4. 제목 키워드 필터는 false positive/negative가 생길 수 있음

- 위치: `app/infrastructure/collectors/google_research_rss_collector.py:28-40`

카테고리 whitelist가 우선이고 제목 키워드가 fallback인 구조는 합리적이다. 다만 `model`, `training`, `inference` 같은 단어는 AI 외 문맥에서도 등장할 수 있고, 반대로 AI 글인데 제목에 키워드가 없고 카테고리가 새 이름으로 바뀌면 누락될 수 있다.

권장:

- 필터로 제외된 항목 수를 로그에 남긴다.
- 추후 category 이름 변화에 대비해 필터 통과/제외 샘플을 주기적으로 확인한다.

## 잘된 점

- Google Research를 DeepMind와 별도 source로 둔 결정은 수집 단계 책임을 명확히 한다.
- RSS 기반이라 HTML scraping보다 유지보수 리스크가 낮다.
- `MAX_ITEMS=50`으로 100건 피드 응답의 수집 볼륨을 제한했다.
- 비-AI 글을 fixture에 포함해 필터 의도를 테스트로 표현하려는 방향은 좋다.
- `metadata`에 `function`, `domain`, `region`, `feed`를 고정해 core-lab origin 소스라는 성격을 남겼다.

## 검증 결과

- `python3 -m pytest tests/test_google_research_collector_golden.py -q`
  - 결과: `ModuleNotFoundError: No module named 'feedparser'`
- `python3 -m pytest -q`
  - 결과: arXiv/Google Research/NVIDIA 테스트 `feedparser` import error로 중단

현재 기준으로 Google Research collector 테스트와 전체 테스트 통과는 확인하지 못했다. 먼저 dependency 환경을 맞추는 것이 필요하다.
