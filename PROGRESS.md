# PROGRESS — Perix Sentinel Refactoring + Collector Revival

기준 문서: `docs/SDD/Perix_Sentinel_Refactoring_SDD.md` / `docs/SDD/Perix_Sentinel_Collector_Revival_SDD.md` / `docs/SDD/Perix_Sentinel_Test_Infra_Mistral_Wrapup_SDD.md` / `docs/SDD/Perix_Sentinel_arXiv_Collector_SDD.md` / `docs/SDD/Perix_Sentinel_HackerNews_Collector_SDD.md` / `docs/SDD/Perix_Sentinel_NVIDIA_Collector_SDD.md`

## 완료된 것

### Refactoring SDD
- **P0 — 특성화 테스트 확보 (R11)** ✅
  - `tests/conftest.py`: `mock_http` fixture (httpx 모듈 레벨 패치 → P1/P2 후에도 유효)
  - `tests/test_scoring_characterization.py`: `calculate_score`/`apply_score` 5케이스 + importance 임계값 고정
  - `tests/test_anthropic_collector_golden.py` + `fixtures/anthropic_news.html` + `.golden.json`
  - `pytest.ini` 추가 (asyncio_mode=auto)
- **P1 — R1·R2·R3 (HTTP/datetime 공통화)** ✅
  - `app/core/datetime_utils.py`: `now_utc()`, `parse_date()`, `try_parse_date()`, `parse_struct_time()`
  - `app/infrastructure/http/async_client.py`: `fetch_html()`, `fetch_json()`, 3회 재시도 + 백오프
  - 전 컬렉터 7개 이전 완료: `datetime.utcnow()` 0건, `import requests` 0건, `aware UTC` 전면 통일
  - `scoring_engine`, `sqlite_item_repository`의 `utcnow` → `now_utc` 완료
  - `tests/test_core_datetime_utils.py`: 23 tests (소스별 날짜 포맷, struct_time, fallback)

### Collector Revival SDD
- **D0 — 진단** ✅ (2026-07-01)
  - GitHub·HuggingFace·DeepMind·Meta → 정상
  - **Mistral 0건 → F3**: Next.js → Astro 전환으로 `__next_f` 임베디드 JSON 소멸
- **D3 — Mistral 파서 재작성** ✅
  - `article[data-title]` 75개, `footer p` 날짜("June 23, 2026"), `h2` 제목, content `p` 설명
  - `urljoin` 사용으로 href 조립 견고화
- **D5 — Mistral 골든 fixture** ✅
  - `tests/fixtures/mistral_news.html` (444KB) + `mistral_news.golden.json` (75건)
  - `tests/test_mistral_collector_golden.py`: 5개 테스트

### arXiv Collector SDD
- **A0 — API 응답 덤프 & 필드 확정** ✅ (2026-07-01)
  - feedparser 키 확인: `id`, `link`, `title`, `summary`, `published_parsed`, `tags`, `authors`, `arxiv_primary_category`, `arxiv_comment`
  - 결정사항: `source="arXiv"`, feedparser 사용, URL=`entry.link`(https, vN 버전 그대로 MVP)
- **A1 — `ArxivApiCollector` 구현** ✅
  - `app/infrastructure/collectors/arxiv_api_collector.py`
  - 카테고리: `cs.AI, cs.CL, cs.LG`, `max_results=50`, 모듈 상수로 명시
  - title/summary 개행·연속공백 정규화 (`re.sub(r'\s+', ' ', text).strip()`)
  - metadata: authors, primary_category, arxiv_id, comment 보존
- **A2 — `collect.py` 등록** ✅
  - `"arxiv": ArxivApiCollector()` 한 줄 추가
- **A3 — 골든 fixture 테스트** ✅
  - `tests/fixtures/arxiv_feed.xml` (3건 실제 응답) + `arxiv_feed.golden.json`
  - `tests/test_arxiv_collector_golden.py`: feedparser.parse monkeypatch → 네트워크 없이 실행
  - **46 passed** (전체 회귀 포함)
- **비범위 준수**: `scoring_policies.py`, `scoring_engine.py` 무변경 확인 ✅
- **A4 — `/collect` 실가동** ✅
  - arXiv 50건 수집, 신규 50건 DB 적재, 5건 briefed
  - DB `source='arXiv'` count = 50, URL/날짜 모두 정상 (aware UTC)
- **arXiv 점수 0**: `SOURCE_WEIGHTS`에 없어 source 점수 0 → **의도된 비범위**(버그 아님)

### Hacker News Collector SDD
- **A0 — API 응답 덤프 & 필드 확정** ✅ (2026-07-01)
  - `time`은 **epoch 초** 확인 (1782842392 → 2026-06-30T17:59:52Z, 현재 날짜와 합치)
  - 39개 샘플 중 1개(url 없는 "Tell HN" 자기글) → **HN 토론 링크 fallback 필요** 확정
  - 39개 모두 `type=story` (job/poll 미관측, 필터는 유지)
  - 전체 키: `score, type, time, text, title, descendants, id, kids, by, url`
- **A1 — `HackerNewsApiCollector` 구현** ✅
  - `app/infrastructure/collectors/hackernews_api_collector.py`
  - 2단계 호출(topstories → item) 모두 공통 `fetch_json` 경유, 직접 httpx 0건
  - `N_TOP=100`, 동시성 `Semaphore(10)`로 매너 throttle
  - AI 키워드 필터: `\b` 단어경계 정규식, 컬렉터 자체 상수(`AI_KEYWORDS`, `KEYWORD_WEIGHTS` 비의존)
  - `url` 없으면 `https://news.ycombinator.com/item?id={id}` fallback
  - `score`/`descendants`/`by`/`hn_id`/`type` → metadata 보존 (나중 popularity 재료)
- **A1.5 — `datetime_utils.from_epoch()` 신설** ✅
  - `app/core/datetime_utils.py`에 공통 함수 추가, 인라인 변환 0건
  - `tests/test_core_datetime_utils.py`: 2 tests 추가 (aware 확인 + 알려진 값 검증)
- **A2 — `collect.py` 등록** ✅
  - `"hackernews": HackerNewsApiCollector()` 한 줄 추가
- **A3 — 골든 fixture 테스트** ✅
  - `tests/fixtures/hackernews_topstories.json` + `hackernews_item_{101,102,103,104}.json` + `hackernews.golden.json`
  - 케이스 매트릭스: AI+url(101) / AI+self-post→fallback(102) / 비AI 필터아웃(103) / job타입 필터아웃(104, 제목에 "AI" 포함해도 걸러짐)
  - `tests/test_hackernews_collector_golden.py`: `mock_http`로 topstories+item 4건 URL 분기 모킹
  - **49 passed** (전체 회귀 포함)
- **비범위 준수**: `scoring_policies.py`, `scoring_engine.py` 무변경 확인 ✅
- **A4 — `/collect` 실가동** ✅
  - HN 12건 수집(topstories 100개 중 AI 필터 통과), 신규 10건 DB 적재
  - 실제 적재 예: "Claude Science", "Claude Code is steganographically marking requests", "New Claude app strings, Fable 5 coming back..." 등 — 필터 정확도 육안 확인
- **HN 점수 0**: `SOURCE_WEIGHTS`에 없어 source 점수 0 → **의도된 비범위**(버그 아님). `score`/`descendants`는 metadata에 보존되어 나중 popularity 설계 시 재사용 가능.

### NVIDIA Collector SDD
- **A0 — 피드 덤프 & 필드 확정** ✅ (2026-07-01)
  - Atom 포맷, `published_parsed` struct_time 정상 채워짐 → `parse_struct_time` 그대로 사용
  - `entry.tags` 존재, `term` 키 → 소문자화 후 tags 리스트에 추가
  - 100건 중 비-AI 4건(4%) → **필터 없음** (SDD §7: <10% 기준 충족)
  - 피드 100건으로 예상(10~30건) 초과 → `MAX_ITEMS=50` 추가
  - summary 필드: HTML 혼입(img 태그) → 원문 그대로 (요약 비범위)
- **A1 — `NvidiaRssCollector` 구현** ✅
  - `app/infrastructure/collectors/nvidia_rss_collector.py`
  - `OpenAIRssCollector` 기반, `RSS_URL`, `source="NVIDIA"`, `MAX_ITEMS=50` 교체
  - `tags = ["nvidia"] + categories` (feedparser entry.tags → term 소문자화)
  - `metadata`: `function/domain/region/feed` 4개 고정
- **A2 — `collect.py` 등록** ✅
  - `"nvidia": NvidiaRssCollector()` 한 줄 추가
- **A3 — 골든 fixture 테스트** ✅
  - `tests/fixtures/nvidia_feed.xml` (3건 실제 Atom 스냅샷) + `nvidia_feed.golden.json`
  - `tests/test_nvidia_collector_golden.py`: feedparser.parse monkeypatch → 네트워크 없이 실행
  - **50 passed** (전체 회귀 포함)
- **A4 — `/collect` 실가동** ✅
  - NVIDIA 50건 수집, 신규 50건 DB 적재. URL/날짜 모두 정상 (aware UTC `+00:00`)
  - `metadata = {"function":"origin","domain":"hardware","region":"us","feed":"developer-blog"}` 확인
  - `tags` 예시: `["nvidia","data center / cloud","data science","cuda-x",...]` 정상
- **비범위 준수**: `scoring_policies.py`, `scoring_engine.py` 무변경 확인 ✅
- **NVIDIA 점수 0**: `SOURCE_WEIGHTS`에 없어 source 점수 0 → **의도된 비범위**(버그 아님). Tier2 재보정 시 처리.

### Test Infra & Wrapup SDD
- **G0 — skip 범위 확정** ✅ → 42 passed, 0 skipped (T1/T2 이미 해결됨)
- **T3 — `/collect` 실가동** ✅
  - 버그 발견: `scoring_engine._recency_score`가 `now`(aware) - `published`(naive) → `TypeError`
  - **수정**: `now.tzinfo`와 `published.tzinfo`를 같은 aware 상태로 정규화 후 비교
  - **결과**: 7/7 소스 DB 적재 성공. DoD(≥6개) 충족.
  - DB 현황: OpenAI 1037·Mistral 75·DeepMind 24·GitHub 19·Anthropic 25·HuggingFace 10·Meta 10
- **T4 — 리뷰 지적 처리** ✅
  - ② `urljoin` 적용 완료 (Mistral 컬렉터)
  - ③ silent date fallback → **공통 부채로 등록** (아래 미결 참조)
- **회귀 테스트 추가** ✅
  - `test_scoring_characterization.py`에 aware/naive 조합 3가지 회귀 케이스 추가
  - **45 passed** (최종)

## 진행 중인 것
- (없음)

## 다음 단계
- Tier1 origin 라인업 완료 (NVIDIA 추가로 hardware 도메인 첫 소스 확보). 갈림길:
  1. **Tier2(뉴스레터·미디어) 수집** — 비교군 데이터, 스코어링 재설계 재료 확보
  2. **P2 (Refactoring SDD)** — `BaseHtmlCollector` 도입, HTML 컬렉터 5개 슬림화

## 미결 결정사항
- **`_recency_score` 정책**: DB에 저장된 구형 naive datetime 문자열 읽기 시 aware 승격 어댑터(SDD R3 §8 완화책) 미구현. 현재 신규 수집 아이템은 모두 aware라 문제 없으나, DB 기존 행 재처리 시 주의 필요.
- **Silent date fallback 가시화 (③ 공통 부채)**: `parse_date()`가 파싱 실패 시 `now_utc()`로 조용히 fallback. 소스마다 개별 수정 대신 **공통 경고 로그 레이어 추가**로 한 번에 해결 예정. P2 또는 전반 정리 라운드에서.
- **P2 범위**: `BaseHtmlCollector` 상속 대상 확정 필요 (Anthropic, DeepMind, GitHub, Meta, Mistral 후보)
- **HN `AI_KEYWORDS` 출처**: 컬렉터 자체 상수로 박음(SDD §5 권고). `scoring_policies.KEYWORD_WEIGHTS`와 키 목록이 미래에 갈라질 수 있음 — Tier1↔Tier2 재설계 시 통합 여부 재논의 필요.
- **진행 방식(합의됨)**: 페이즈마다 멈춰서 확인. 그린이어도 자동 다음 페이즈 진행하지 않음.
