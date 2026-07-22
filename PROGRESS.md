# PROGRESS — Perix Sentinel Refactoring + Collector Revival

기준 문서: `docs/SDD/Perix_Sentinel_Refactoring_SDD.md` / `docs/SDD/Perix_Sentinel_Collector_Revival_SDD.md` / `docs/SDD/Perix_Sentinel_Test_Infra_Mistral_Wrapup_SDD.md` / `docs/SDD/Perix_Sentinel_arXiv_Collector_SDD.md` / `docs/SDD/Perix_Sentinel_HackerNews_Collector_SDD.md` / `docs/SDD/Perix_Sentinel_NVIDIA_Collector_SDD.md` / `docs/SDD/Perix_Sentinel_GoogleResearch_Collector_SDD.md` / `docs/SDD/Perix_Sentinel_HF_RegionTagging_SDD.md` / `docs/SDD/Tier2 data collectors/Perix_Sentinel_TechCrunch_Collector_SDD.md` / `docs/SDD/Tier2 data collectors/Perix_Sentinel_MarkTechPost_Collector_SDD.md` / `docs/SDD/Clustering/Perix_Sentinel_Clusterer_Event_SDD.md` / `docs/SDD/Clustering/Perix_Sentinel_Clusterer_Impl_SDD_A2a_A3.md`

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

### Google Research Collector SDD
- **A0 — 피드 덤프 & 필드 확정** ✅ (2026-07-01)
  - Canonical `https://research.google/blog/rss` ✅ RSS 2.0, bozo=False
  - `published_parsed` struct_time 정상 → `parse_struct_time` 그대로
  - `entry.tags` 있음, `term` 키 소문자화
  - **비-AI 비율 25% (>15% 임계값) → 필터 적용** (SDD §7)
  - 피드 100건 → `MAX_ITEMS=50` 추가
  - summary = 카테고리 이름 텍스트만(짧음) → 원문 그대로 (비범위)
- **A1 — `GoogleResearchRssCollector` 구현** ✅
  - `app/infrastructure/collectors/google_research_rss_collector.py`
  - `NvidiaRssCollector` 기반, `RSS_URL`, `source="Google Research"`, `MAX_ITEMS=50` 교체
  - `_AI_CATEGORIES` 화이트리스트(machine intelligence, generative ai, nlp, open source models & datasets, responsible ai) + `_AI_KEYWORD_RE` 제목 폴백
  - `tags = ["google-research"] + categories`, `metadata`: `function/domain(core-lab)/region/feed` 4개 고정
- **A2 — `collect.py` 등록** ✅
  - `"google_research": GoogleResearchRssCollector()` 한 줄 추가
- **A3 — 골든 fixture 테스트** ✅
  - `tests/fixtures/google_research_feed.xml` (4건: AI 통과 3건 + 비-AI 필터아웃 1건) + `google_research_feed.golden.json`
  - `tests/test_google_research_collector_golden.py`: 2개 테스트 (golden match + non-AI filtered)
  - **52 passed** (전체 회귀 포함)
- **A4 — `/collect` 실가동** ✅
  - Google Research 45건 수집, 신규 44건 DB 적재. URL/날짜 모두 정상 (aware UTC `+00:00`)
  - `metadata = {"function":"origin","domain":"core-lab","region":"us","feed":"research-blog"}` 확인
  - `tags` 예시: `["google-research","climate & sustainability","earth ai","open source models & datasets"]` 정상
- **비범위 준수**: `scoring_policies.py`, `scoring_engine.py` 무변경 확인 ✅
- **Google Research 점수 0**: `SOURCE_WEIGHTS`에 없어 source 점수 0 → **의도된 비범위**(버그 아님). Tier2 재보정 시 처리.
- **DeepMind 의미중복**: `deepmind.google`와 `research.google`는 별개 조직·별개 소스로 유지. URL이 달라 url_hash dedup 미발동 → 의미 중복 병합은 Clusterer로 이월.

### HF Region Tagging SDD
- **A0 — 실제 HF author 핸들 표기 확인** ✅ (2026-07-01)
  - author = `model_id.split("/")[0]` 원래 대소문자 그대로 (`Qwen`, `zai-org`)
  - `_derive_region`에서 `author.lower()`로 정규화 → SDD 상수 그대로 사용 가능
  - A0 실측에서 `baidu`(중국 조직) 트렌딩 등장 → SDD 미포함이므로 구현엔 미추가, 미결에 기록
- **A1+A2 — `HuggingFaceApiCollector` 수정** ✅
  - `_ORG_REGION` (조직 핸들 → region, 정확 일치), `_FAMILY_REGION` (모델 패밀리 substring → region, 2차) 상수 추가
  - `_derive_region(author, model_id)`: 1차(org) → 2차(substring) → `global` 폴백
  - metadata에 `function=origin`, `domain=ecosystem`, `region=<파생>` 추가
- **A3 — HF 골든 fixture 신규 작성** ✅
  - `tests/fixtures/huggingface_trending.json` (4건: cn조직/cn재업로드/us/global)
  - `tests/fixtures/huggingface_trending.golden.json`
  - `tests/test_huggingface_collector_golden.py`: 6개 테스트 (golden match + 4 region 케이스 + function/domain 전체 확인)
  - **58 passed** (전체 회귀 포함)
- **A4 — 실가동 확인** ✅
  - `zai-org/GLM-5.2` → region=cn (1차 org) ✅
  - `Qwen/Qwen-AgentWorld-35B-A3B` → region=cn (1차 org, Qwen→lower 정규화) ✅
  - `yuxinlu1/gemma-4-12B-...` → region=us (2차 substring `gemma`) ✅
  - `function=origin`, `domain=ecosystem` 전 항목 정상 ✅
- **비범위 준수**: `scoring_policies.py`, `scoring_engine.py` 무변경 확인 ✅
- **HF region=global 기본값**: 알 수 없는 조직은 `global` — HF 전역 허브 성격 반영 (의도된 설계)
- **타 컬렉터 region 백필은 별건**: OpenAI(`us`)·arXiv(`global`) 등 기존 컬렉터 `function/domain/region` 소급은 다음 작업으로 분리

### MarkTechPost Collector SDD (Tier2 coverage, 두 번째 소스)
- **A0 — 피드 덤프 & 필드 확정** ✅ (2026-07-21)
  - `https://www.marktechpost.com/feed/` RSS 2.0, bozo=False
  - 10건 전부 AI 관련 카테고리 보유(비-AI 0%, SDD 예상대로 <15% 임계값 이하) → **카테고리 필터 불필요**
  - `published_parsed` 정상 채워짐(UTC)
  - `<img>` 혼입은 없음(Google Research 때와 달리 정제 불필요). 다만 WordPress boilerplate(`The post ... appeared first on MarkTechPost.`)에 `<a href=...>` 링크 HTML이 포함되며, 원문 그대로 유지한다
  - SDD §6 가정과 실측 100% 일치 → §6·§7 갱신 불필요
- **A1~A3 — `MarkTechPostRssCollector` 구현 + 배선** ✅
  - `app/infrastructure/collectors/marktechpost_rss_collector.py` — `TechCrunchRssCollector` 복사 기반, `RSS_URL`/`source="MarkTechPost"`/`metadata.feed="marktechpost-ai"` 교체
  - `app/interface/api/collect.py`의 `/collect/coverage` 딕셔너리에 `"marktechpost"` 한 줄 추가 (신규 엔드포인트·신규 러너 없음)
- **A4 — 골든 fixture + 실가동** ✅
  - `tests/fixtures/marktechpost_feed.xml`(A0 실제 덤프 3건 트림, 카테고리 포함) + `marktechpost_feed.golden.json`
  - `tests/test_marktechpost_collector_golden.py`: golden match + 브리핑 0건 배선 테스트 2개
  - **62 passed** (전체 회귀 포함, 기존 60 + 신규 2)
  - `/collect/coverage` 실가동: TechCrunch 20건 + MarkTechPost 10건 모두 DB 적재, **briefed=0** 확인
- **비범위 준수**: `scoring_policies.py`, `scoring_engine.py` 무변경 확인 ✅, 신규 유틸·신규 엔드포인트 0
- **Clusterer 입력 데이터 다양성 확보**: coverage 소스가 TechCrunch(속보) + MarkTechPost(모델 릴리스 요약, origin과 내용 밀도 가장 근접) 2개로 늘어 — 다음 SDD(Clusterer + Event 모델)에서 "origin 하나에 여러 echo 매칭" 케이스 실전 검증 가능

### Clusterer + Event 모델 SDD
- **A0 — 실데이터 관측** ✅ (2026-07-21, 상세는 `docs/notes/clusterer-event-a0-observation.md`)
  - **ground truth 0쌍 확인 — 구조적 원인.** 기존 DB는 origin 백필(~06-30)과 coverage(07-17~) 시간창이 아예 겹치지 않았음. 사용자 승인 하에 origin `/collect` 라이브 실행(부수효과: Discord에 38건 실제 브리핑 발행)으로 시간대는 겹치게 됐으나, SDD §2.3 게이트를 실제 적용해도 확정 매칭 여전히 0쌍. Org만 겹치는 후보 5쌍을 사람이 직접 검토했으나 전부 실제로는 다른 사건.
  - 근본 원인: (1) origin 컬렉터 세트가 coverage가 다루는 조직(Alibaba·Moonshot·DeepSeek·Zhipu)을 커버 안 함, (2) 겹치는 조직(OpenAI 등)도 조직명만으로는 오탐 다발 — SDD가 이미 예견한 리스크가 실측으로 재현됨.
  - 개체 추출 정밀도: 조직 매칭 22/100(양호). 모델 정규식은 10건 중 3건 오탐(`February 2026`, `Scholars 2020`, `AutoScout24`) — SDD가 경고한 오탐 패턴 실측 재현. A2 착수 시 날짜 패턴 가드 필요.
  - 배포 형태: 단일 Docker 컨테이너 확인 → APScheduler(인프로세스) 결정.
  - **결정: A2(clusterer.py 로직 + 골든 테스트)는 보류.** 재개 조건은 노트 참조.
- **A1 — Event 모델/포트/어댑터** ✅ (ground truth와 무관한 순수 구조 작업이라 보류 없이 진행)
  - `app/domain/models/event.py` — `Event`·`EventMember` (SDD §5.1 그대로)
  - `app/domain/ports/event_repository.py` — `EventRepositoryPort`
  - `app/infrastructure/repositories/sqlite_event_repository.py` — `events` 테이블 + 인덱스 2개(§5.2), `event_id` 기준 upsert로 멱등성 확보
  - `app/main.py` lifespan에 `SqliteEventRepository().init_db()` 추가 (기존 `SqliteItemRepository`와 동일 패턴), 실제 `perix_sentinel.db`에 `events` 테이블 생성 라이브 확인
  - `tests/test_event_repository.py` 4종(round-trip/멱등성/mark_briefed/미존재 조회) — **66 passed** (기존 62 + 신규 4)
  - A2(클러스터링 로직·`get_unbriefed_since`·`DailyBriefingUseCase`·엔드포인트·스케줄러)는 미착수

### Clusterer 구현 SDD (A2a + A3) — v0.2
- **P0 — A1 리뷰 지적 2건 수정** ✅ (2026-07-21)
  - `SqliteEventRepository.upsert()`: `ON CONFLICT` 절에서 `is_briefed`/`briefed_at`을 `CASE WHEN` 단조 증가로 변경 — 이미 브리핑된 Event가 재클러스터링으로 되돌아가지 않음
  - 빈 `event_id` upsert 시 `ValueError` 발생하도록 가드 추가
  - `tests/test_event_repository.py`에 회귀 테스트 2개 추가
- **P1 — 개체 추출 v2** ✅
  - `app/domain/services/entity_extractor.py` 신규 (순수 함수, I/O 없음)
  - 조직 사전(`_ORG_ALIASES`) + 모델 패밀리 화이트리스트(`_MODEL_FAMILIES`) — SDD §2.1 결정대로 정규식 단독 방식 폐기
  - 토크나이저에 아포스트로피(`'`)도 구분자로 추가(SDD에 없는 사항, "OpenAI's ..." 류 소유격 헤드라인에서 조직명 토큰이 깨지는 것을 막기 위한 최소 보강)
  - `tests/test_entity_extractor.py`: 조직/모델 변형/A0 오탐 3종 배제 — 3 tests
  - **실DB 100건 재측정(라이브 `perix_sentinel.db`, 1615건 중 랜덤 100)**: 모델 오탐 **0건** 확인(A0의 `February 2026`/`Scholars 2020`/`AutoScout24` 패턴 재현 안 됨) — DoD 충족
- **P2 — clusterer.py** ✅
  - `app/domain/services/clusterer.py` 신규 — `cluster(items) -> list[Event]`, I/O·DB 접근 0
  - 3게이트(시간창 +48h/-6h → 개체 교집합 → 제목 Jaccard 타이브레이커) + HF 게이트3 예외(비-HF 우선) 구현
  - `event_id = md5(origin.url_hash)`로 생성 강제(빈 값 발생 불가)
  - `app/core/config.py`에 `MATCH_WINDOW_AFTER_H=48`, `MATCH_WINDOW_BEFORE_H=6` 모듈 상수 추가
  - `tests/test_clusterer.py`: 7 tests — A0 음성 5쌍(실제 제목은 재구성, 원문 그대로는 아님) 전부 미매칭, 시간창 경계(+49h/-7h 탈락·+47h/-5h 통과), 개체 게이트, 타이브레이커, HF 예외, 단일귀속, `event_id` 멱등성
- **P2 구현 리뷰 반영 (2026-07-21, `docs/notes/clusterer-impl-review.md`)** ✅ — 리뷰 지적 3건 + 사용자 결정 반영
  1. **게이트2 unique-candidate 판정 기준 수정**: "시간창 내 전체 후보 수" → "시간창 내 **같은 조직** 후보 수"로 변경(`clusterer.py`의 `org_overlap_count`). 기존 방식은 무관한 조직의 origin이 같은 시간창에 있다는 이유만으로 유일 후보 판정이 깨져 false negative를 유발했음(예: OpenAI coverage가 모델명 없이도 OpenAI origin에 붙어야 하는데, 시간창에 무관한 NVIDIA origin이 있으면 실패). 회귀 테스트 `test_clusterer_unique_candidate_is_per_org_not_per_window` 추가 — 수정 전 로직으로는 실패함을 확인.
  2. **`EventMember.item_id` → `item_hash`로 개명**: 필드가 DB 정수 id가 아니라 `CollectedItem.url_hash`라는 사실을 타입/이름 레벨에서 명확히 함(사용자 결정, "지금이 무료"). `event.py`/`sqlite_event_repository.py`/`clusterer.py`/테스트 전체 갱신.
  3. **`ItemRepositoryPort.mark_briefed(item_id: int)` 폐기 → `mark_briefed_by_hash(url_hash: str)` 신설**: `SqliteItemRepository`(WHERE url_hash=?), `CollectTrendsUseCase` 갱신. 사용자 결정에 따라 A3의 `get_unbriefed_since()`는 DB 정수 id를 싣지 않고 `CollectedItem`(url_hash 포함)만 반환하는 방향으로 §7.1 미결 사항이 해소됨 — 브리핑 완료 표시는 항상 url_hash 기준.
  - **층화 재측정(P1 DoD 실질 충족)**: 단순 랜덤 100건은 OpenAI가 DB의 65%를 차지해 편향 위험 → arXiv 30 / GitHub Trending 20 / Hacker News 20 / 나머지 소스 30건으로 층화 재추출. 모델 히트 13건(Hacker News 8, OpenAI 5), **오탐 0건** — arXiv·GitHub 히트 0건은 두 소스의 제목이 브랜드 모델명을 잘 언급하지 않는 정상적인 재현율 특성(회귀 아님).
- **전체 회귀**: 66 + 13(P0 2 + P1 3 + P2 8) = **79 passed**
- **A3(Phase 2 배선: `get_unbriefed_since`/`DailyBriefingUseCase`/`CollectTrendsUseCase` 정리/스케줄러)는 SDD §8 "P2에서 한 번 끊는다" 지시에 따라 미착수** — 사용자 확인 후 진행

### Origin-Origin 중복 A0 관측 (신규, 2026-07-22, `docs/notes/clusterer-origin-origin-a0-observation.md`)
- **실측 결과: origin 소스끼리(같은 조직 언급 후보) 705쌍 중 48h 시간창 내 35쌍, 그중 실제 동일 사건은 1쌍뿐 (Anthropic "Claude Science" ↔ Hacker News "Claude Science", Δt=17.1h)**
- **결정: origin-origin 중복 병합 SDD는 지금 작성하지 않는다.** 표본 1건으로 임계값(시간창/jaccard)을 정하면 검증 불가능한 추측이 됨 — origin-vs-coverage A0(07-21)와 동일한 구조적 결론 재현.
- **부수 발견**: `entity_extractor.tokenize()`가 `,`를 구분자로 처리하지 않아 트레일링 콤마 토큰이 jaccard를 실제보다 낮게 만듦 (유일한 진짜 양성 쌍이 jaccard=0.09로 최하위권 — jaccard를 1차 게이트로 쓰면 안 되는 근거 재확인, 콤마 제거 시 0.20으로 상승 확인).
- **재개 조건**: 2주 추가 관측 후 재평가(A2b와 같은 주기), 또는 임계값 없는 "org overlap + ≤48h + 사람 확인 큐" 저위험 휴리스틱만 우선 검토.
- **콤마 버그 수정 후 재실행 확인 (2026-07-22)**: 후보 수(705쌍/48h창 35쌍) 불변, 진짜 양성 쌍 jaccard만 0.09→0.20 정정, 진짜 동일사건 여전히 1건. **0.06% 중복률은 측정 아티팩트가 아니라 실측치로 확정.** 최고 jaccard(0.27)가 여전히 가짜라는 점도 재확인 — jaccard 1차 게이트 불가 결론 유지.

### Origin ↔ TechCrunch 재측정 (신규, 2026-07-22, `docs/notes/clusterer-origin-coverage-a0-rerun.md`)
- **프로덕션 gate1(-6h/+48h, `clusterer.py` 실제 함수 재사용) + org 교집합: 매칭 0쌍 (0/20 TechCrunch row)** — 07-21 라이브 재확인과 동일 결론 재현.
- 시간창 무제한 org-only 매칭은 230쌍 나오지만 229쌍이 Δt 168h 초과("openai" 조직명만으로 OpenAI 아카이브 1,059건과 무차별 매칭), 가장 근접한 쌍(Δt=115.6h)조차 실제로는 무관한 사건 — 대표 5케이스 전부 오탐 확인.
- **결론 변경 없음**: origin↔coverage 자동 병합 SDD는 여전히 실증 근거 없음.

## 진행 중인 것
- (없음 — P2 게이트에서 정지, 사용자 확인 대기)

## 다음 단계
- **A3 착수 여부 확인** — 승인 시 `get_unbriefed_since`(item id 전달 방식 확정 포함) → `DailyBriefingUseCase` → `CollectTrendsUseCase` 정리 → `BriefingGenerator` Event digest → `/briefing/run` → APScheduler 순으로 진행(SDD §8 P3~P5)
- **A2b(양성 골든 fixture) 재평가는 2주 관측 후** — 기존 origin 소스(OpenAI·Anthropic·Google·Meta·Mistral·NVIDIA)의 메이저 릴리스가 자연 발생해 게이트2를 통과하는 실제 쌍이 나오는지 관찰 (SDD §1.3, 기존 "origin 컬렉터 확장" 재개 조건은 폐기됨 — HF region 흡수 결정과 충돌하기 때문)
- Tier2 coverage 소스 2개(TechCrunch·MarkTechPost) 확보 완료. 그 외 갈림길:
  1. **타 컬렉터 region 백필 (SDD §8)** — OpenAI·Anthropic·arXiv·HN 등 기존 컬렉터에 `function/domain/region` 상수 태그 추가 (HF와 달리 전부 상수라 간단)
  2. **나머지 coverage 소스(MIT TR·Verge·Decoder)** — 각각 별도 SDD
  3. **P2 (Refactoring SDD)** — `BaseHtmlCollector` 도입, HTML 컬렉터 5개 슬림화

## 미결 결정사항
- **`_recency_score` 정책**: DB에 저장된 구형 naive datetime 문자열 읽기 시 aware 승격 어댑터(SDD R3 §8 완화책) 미구현. 현재 신규 수집 아이템은 모두 aware라 문제 없으나, DB 기존 행 재처리 시 주의 필요.
- **Silent date fallback 가시화 (③ 공통 부채)**: `parse_date()`가 파싱 실패 시 `now_utc()`로 조용히 fallback. 소스마다 개별 수정 대신 **공통 경고 로그 레이어 추가**로 한 번에 해결 예정. P2 또는 전반 정리 라운드에서.
- **P2 범위**: `BaseHtmlCollector` 상속 대상 확정 필요 (Anthropic, DeepMind, GitHub, Meta, Mistral 후보)
- **HN `AI_KEYWORDS` 출처**: 컬렉터 자체 상수로 박음(SDD §5 권고). `scoring_policies.KEYWORD_WEIGHTS`와 키 목록이 미래에 갈라질 수 있음 — Tier1↔Tier2 재설계 시 통합 여부 재논의 필요.
- **진행 방식(합의됨)**: 페이즈마다 멈춰서 확인. 그린이어도 자동 다음 페이즈 진행하지 않음.
- **`baidu` HF region 미포함**: A0에서 `baidu/Unlimited-OCR`이 트렌딩에 등장. `baidu`는 중국 조직이나 SDD `_ORG_REGION` 목록에 없어 현재 `global`. `_ORG_REGION` 확장 시 추가 필요.
- **타 컬렉터 region 백필 미구현**: OpenAI·Anthropic·arXiv·HN·NVIDIA·GR 등 기존 컬렉터에 `function/domain/region` 상수 태그 없음. SDD §8 다음 작업으로 분리됨.
- **MarkTechPost boilerplate와 Clusterer 매칭 오염**: `summary` 말미에 모든 항목 공통 상수 문자열(`The post <a href=...>...</a> appeared first on <a href=...>MarkTechPost</a>.`)이 붙는다. **해결됨(설계 차원)**: Clusterer + Event 모델 SDD §2.6이 매칭 입력을 `title`로 한정하기로 결정해 이 문제를 회피한다. `summary`는 브리핑 렌더링에만 쓰인다.
- **RSS `t["term"]` 직접 접근 가용성 리스크**: OpenAI·NVIDIA·Google Research·TechCrunch·MarkTechPost 5개 컬렉터가 `t["term"]` 직접 접근 동일 패턴. tag object에 `term` 키가 없으면 entry 하나 때문에 `collect()` 전체가 `KeyError`로 중단된다. 스타일 부채가 아니라 **가용성 리스크**로 격상해 기록. 공통 정리 라운드에서 `t.get("term")` 방어적 helper로 통합 검토.
- **Coverage 피드 페이지 크기 제약(MTP 10건/TC 20건) → 수집 주기 대비 유실 가능. Clusterer 설계 시 cadence 결정 필요**
- ~~**Clusterer ground truth 부재**~~ — **해결(재정의)**: Clusterer 구현 SDD v0.2 §1.1이 "양성 쌍 0개"와 "clusterer 로직 검증"을 분리 — 음성 쌍 5건 + 경계 테스트로 A2a(로직)는 진행 가능하다고 재해석함. A2b(양성 골든)만 2주 관측 후 재평가로 이월(위 "다음 단계" 참조).
- ~~**모델 추출 정규식 오탐**~~ — **해결**: `_MODEL_RE` 정규식 폐기, `app/domain/services/entity_extractor.py`의 조직 사전+모델 패밀리 화이트리스트로 교체. 실DB 100건 재측정에서 오탐 0건 확인(위 P1 참조).
- ~~**`item_id`가 int가 아닌 `url_hash`(str) 사용**~~ — **해결(결정됨, 2026-07-21)**: `EventMember.item_id` → `item_hash`로 개명, `ItemRepositoryPort.mark_briefed(item_id: int)` → `mark_briefed_by_hash(url_hash: str)`로 교체. A3의 `get_unbriefed_since()`는 DB 정수 id를 아예 싣지 않고 `CollectedItem`만 반환하는 방향으로 확정 — url_hash가 이미 UNIQUE 컬럼이라 브리핑 완료 표시에 충분함.
- **HF title 구조 문제 (신규, 2026-07-21)**: HuggingFace 컬렉터의 `title`이 `model_id`(예: `"bartowski/Qwen3.6-GGUF"`)라 자연어 헤드라인과 다르다. 게이트3(Jaccard)는 SDD §2.2 결정대로 건너뛰지만, 업로더가 원저작자와 다른 경우(제3자 파인튜닝/양자화) 조직 개체 추출 자체가 비어버릴 수 있음(A0 pair #4가 실측 사례) — A2b 양성 데이터 확보 시 재검토 필요.
- **`int`→`str` ID 전면 전환 미결**: `ItemRepositoryPort.get_by_id(item_id: int)`는 여전히 정수 id를 쓰고, `EventMember.item_hash`는 문자열 url_hash를 쓴다 — 두 ID 체계가 공존한다. 전면 전환은 비범위(SDD §4)로 부채만 기록.
- **`entity_extractor.py`의 넓은 alias 중첩 (신규, 2026-07-21, `clusterer-impl-review.md` #2)**: `"command"`가 Cohere 조직 alias이자 모델 패밀리로 동시에 등록돼 있어, 일반 문장의 "command"가 `org={"cohere"}`+`model={("command","")}`로 오추출될 위험이 있음. `"phi"`/`"meta"`도 비슷한 다의성 위험. 실DB 층화 100건 재측정(arXiv30·GitHub20·HN20·기타30)에서는 오탐 0건이었으나, 장기 운영 샘플에서 별도 카운트로 관찰 필요 — 아직 가드 미적용.
- **토크나이저 아포스트로피 처리 (신규, 2026-07-21, SDD에 없던 보강)**: `entity_extractor.tokenize()`가 SDD §5 명세에 없는 아포스트로피(`'`)도 구분자로 처리하도록 확장함 — "OpenAI's GPT-5.5" 같은 소유격 헤드라인에서 조직명이 `"openai's"` 한 토큰으로 붙어버려 별칭 매칭이 깨지는 것을 막기 위함. 리뷰 시 SDD 갱신 여부 확인 필요.
- ~~**토크나이저 콤마 미처리**~~ — **해결 (2026-07-22)**: `entity_extractor.py`의 `_SEP_RE`에 `,` 추가(`[-_/',]`). `tests/test_entity_extractor.py::test_tokenize_strips_trailing_comma` 회귀 테스트 추가. **80 passed** (기존 79 + 신규 1).
- **Origin-origin 중복 SDD 보류 (신규, 2026-07-22)**: 위 관측대로 실제 origin-origin 중복 표본이 1건뿐이라 SDD 작성을 보류함. 2주 재관측 또는 임계값 없는 휴리스틱 우선 검토가 재개 조건.
