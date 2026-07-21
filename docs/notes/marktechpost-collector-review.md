# MarkTechPost Collector 리뷰

작성일: 2026-07-21

## 요약

이번 변경은 Tier2 coverage 두 번째 소스로 `MarkTechPostRssCollector`를 추가하고, 기존 `/collect/coverage` store-only 경로에 `"marktechpost": MarkTechPostRssCollector()`를 등록하는 작업이다. 구현은 `TechCrunchRssCollector` 복사 기반으로 RSS URL, source, tags, metadata feed 값만 교체한 형태이며, coverage 항목은 `publisher=None` 배선으로 저장만 되고 브리핑되지 않는다.

## 주요 리뷰 의견

### 1. `PROGRESS.md`의 summary HTML 설명이 fixture와 다름

- 위치: `PROGRESS.md:175`
- 관련 fixture: `tests/fixtures/marktechpost_feed.golden.json`

`PROGRESS.md`에는 `summary`에 `<img>` 등 HTML 혼입이 없고 WordPress boilerplate만 포함된다고 적혀 있다. 실제 golden fixture에는 `<img>`는 없지만 `The post ... appeared first on MarkTechPost.` boilerplate 안에 `<a href=...>` HTML 링크가 포함되어 있다.

필요 조치:

- 문구를 "`<img>` 혼입은 없음. 다만 WordPress boilerplate의 `<a>` 링크 HTML은 원문 그대로 유지"처럼 수정한다.
- 이 동작이 의도라면 fixture가 현재 계약을 잘 고정하고 있으므로 코드 정제는 필요 없다.

### 2. 신규 구현 파일들이 untracked 상태라 `git diff`만으로는 구현 검토가 누락됨

- 확인 명령: `git status --short`
- 상태: collector, SDD, fixture, test 파일이 untracked

현재 `git diff`에는 `PROGRESS.md`와 `app/interface/api/collect.py` 변경만 보인다. 실제 구현 핵심인 `app/infrastructure/collectors/marktechpost_rss_collector.py`와 테스트 파일들은 아직 Git 추적 대상이 아니어서 커밋/PR 시 누락될 수 있다.

필요 조치:

- 아래 파일들을 커밋 전에 명시적으로 stage한다.
- `app/infrastructure/collectors/marktechpost_rss_collector.py`
- `docs/SDD/Tier2 data collectors/Perix_Sentinel_MarkTechPost_Collector_SDD.md`
- `tests/fixtures/marktechpost_feed.xml`
- `tests/fixtures/marktechpost_feed.golden.json`
- `tests/test_marktechpost_collector_golden.py`

### 3. categories 파싱은 기존 RSS 컬렉터와 같은 약한 지점이 있음

- 위치: `app/infrastructure/collectors/marktechpost_rss_collector.py:33-35`

현재 코드는 `categories = [t["term"].lower() for t in raw_tags]`로 직접 접근한다. fixture와 현재 feedparser 출력에서는 정상 동작하지만, feed tag object에 `term`이 없으면 한 entry 때문에 수집 전체가 `KeyError`로 중단될 수 있다.

권장:

- 기존 TechCrunch와 같은 패턴을 유지한 것은 이번 변경 범위에서는 타당하다.
- RSS 컬렉터 공통 정리 시 `term = t.get("term")` 형태의 방어적 helper로 묶는 것을 검토한다.

## 잘된 점

- `/collect/coverage` 기존 store-only 경로에만 등록해 coverage 항목이 Discord 브리핑으로 나가지 않는 불변식을 유지했다.
- `metadata`에 `function=coverage`, `domain=media`, `region=us`, `feed=marktechpost-ai`를 고정해 향후 Clusterer가 coverage 항목을 찾기 쉽다.
- 신규 엔드포인트, 신규 runner, scoring 변경 없이 기존 아키텍처를 재사용했다.
- golden fixture가 실제 MarkTechPost RSS 구조의 카테고리, UTC publish time, WordPress summary boilerplate를 함께 고정한다.
- `tests/test_marktechpost_collector_golden.py`가 parser output과 `publisher=None` 시 브리핑 0건 계약을 둘 다 확인한다.

## A0 비-AI 비율 실측 (2026-07-21)

- 측정 대상: `https://www.marktechpost.com/feed/` 라이브 덤프
- **주의**: 피드 자체가 WordPress 기본 페이지 크기인 **10건만** 반환한다 (`MAX_ITEMS=50`은 상한일 뿐, 실제 feed.entries 길이가 10). "50건 기준" 측정은 소스 쪽 제약으로 불가능해 **실측 가능한 전량(10건)**으로 산출했다.
- 판정 기준: 각 entry의 `<category>` 태그 집합에 AI 직접 마커(`artificial intelligence`, `ai shorts`, `ai infrastructure`, `ai agents`, `agentic ai`, `machine learning`, `language model`, `large language model`, `llm`)가 하나라도 있으면 AI-tagged로 분류.
- **결과: 비-AI 0건 / 10건 = 0%** — 10건 전부 AI 직접 카테고리 보유.
- 판단: Google Research 선례의 임계값(15%)을 크게 하회 → **카테고리 서브피드 전환 불필요**, SDD §5의 "매체 전체가 AI 전문"이라는 가정이 실측으로 확인됨. §5·§7 갱신 불필요.
- 한계: 표본이 10건으로 작아(Google Research·NVIDIA 등 100건 표본 대비) 통계적 신뢰도는 낮다. 페이지네이션(`?paged=N`)으로 표본을 늘리는 것은 이번 마무리 작업 범위 밖이므로, 향후 비-AI 콘텐츠가 실제로 관측되면 재측정한다.

## 검증 결과

- `.venv/bin/pytest tests/test_marktechpost_collector_golden.py`
  - 결과: `2 passed, 16 warnings`
- `.venv/bin/pytest`
  - 결과: `62 passed, 72 warnings`
- `python3 -m pytest tests/test_marktechpost_collector_golden.py`
  - 결과: 기본 Python 환경에서는 `ModuleNotFoundError: No module named 'feedparser'`

테스트는 프로젝트 `.venv` 기준으로 통과한다. 기본 Python 환경은 requirements가 설치되어 있지 않아 feedparser import 단계에서 실패하므로, 향후 검증 명령은 `.venv/bin/pytest` 기준으로 명시하는 것이 맞다.
