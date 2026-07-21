# PROGRESS — Perix Sentinel Refactoring + Collector Revival

기준 문서: `docs/SDD/Perix_Sentinel_Refactoring_SDD.md` / `docs/SDD/Perix_Sentinel_Collector_Revival_SDD.md` / `docs/SDD/Perix_Sentinel_Test_Infra_Mistral_Wrapup_SDD.md` / `docs/SDD/Perix_Sentinel_arXiv_Collector_SDD.md` / `docs/SDD/Perix_Sentinel_HackerNews_Collector_SDD.md` / `docs/SDD/Perix_Sentinel_NVIDIA_Collector_SDD.md` / `docs/SDD/Perix_Sentinel_GoogleResearch_Collector_SDD.md` / `docs/SDD/Perix_Sentinel_HF_RegionTagging_SDD.md` / `docs/SDD/Tier2 data collectors/Perix_Sentinel_TechCrunch_Collector_SDD.md` / `docs/SDD/Tier2 data collectors/Perix_Sentinel_MarkTechPost_Collector_SDD.md`

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

## 진행 중인 것
- (없음)

## 다음 단계
- Tier2 coverage 소스 2개(TechCrunch·MarkTechPost) 확보 완료. 갈림길:
  1. **Clusterer + Event 모델 SDD** — 이 세션 MarkTechPost SDD의 명시된 후속 과제. origin↔coverage 매칭 설계 착수
  2. **타 컬렉터 region 백필 (SDD §8)** — OpenAI·Anthropic·arXiv·HN 등 기존 컬렉터에 `function/domain/region` 상수 태그 추가 (HF와 달리 전부 상수라 간단)
  3. **나머지 coverage 소스(MIT TR·Verge·Decoder)** — 각각 별도 SDD
  4. **P2 (Refactoring SDD)** — `BaseHtmlCollector` 도입, HTML 컬렉터 5개 슬림화

## 미결 결정사항
- **`_recency_score` 정책**: DB에 저장된 구형 naive datetime 문자열 읽기 시 aware 승격 어댑터(SDD R3 §8 완화책) 미구현. 현재 신규 수집 아이템은 모두 aware라 문제 없으나, DB 기존 행 재처리 시 주의 필요.
- **Silent date fallback 가시화 (③ 공통 부채)**: `parse_date()`가 파싱 실패 시 `now_utc()`로 조용히 fallback. 소스마다 개별 수정 대신 **공통 경고 로그 레이어 추가**로 한 번에 해결 예정. P2 또는 전반 정리 라운드에서.
- **P2 범위**: `BaseHtmlCollector` 상속 대상 확정 필요 (Anthropic, DeepMind, GitHub, Meta, Mistral 후보)
- **HN `AI_KEYWORDS` 출처**: 컬렉터 자체 상수로 박음(SDD §5 권고). `scoring_policies.KEYWORD_WEIGHTS`와 키 목록이 미래에 갈라질 수 있음 — Tier1↔Tier2 재설계 시 통합 여부 재논의 필요.
- **진행 방식(합의됨)**: 페이즈마다 멈춰서 확인. 그린이어도 자동 다음 페이즈 진행하지 않음.
- **`baidu` HF region 미포함**: A0에서 `baidu/Unlimited-OCR`이 트렌딩에 등장. `baidu`는 중국 조직이나 SDD `_ORG_REGION` 목록에 없어 현재 `global`. `_ORG_REGION` 확장 시 추가 필요.
- **타 컬렉터 region 백필 미구현**: OpenAI·Anthropic·arXiv·HN·NVIDIA·GR 등 기존 컬렉터에 `function/domain/region` 상수 태그 없음. SDD §8 다음 작업으로 분리됨.
- **MarkTechPost boilerplate와 Clusterer 매칭 오염**: `summary` 말미에 모든 항목 공통 상수 문자열(`The post <a href=...>...</a> appeared first on <a href=...>MarkTechPost</a>.`)이 붙는다. Clusterer가 텍스트 유사도로 origin↔coverage를 매칭할 때 (i) MarkTechPost 항목끼리 유사도가 인위적으로 상승, (ii) origin 항목과의 유사도는 상대적으로 희석 — 두 방향 모두 오탐 요인이 될 수 있다. 지금은 정제하지 않고 수집 계약을 고정 유지하되, Clusterer SDD의 A0 관측 항목으로 이월한다.
- **RSS `t["term"]` 직접 접근 가용성 리스크**: OpenAI·NVIDIA·Google Research·TechCrunch·MarkTechPost 5개 컬렉터가 `t["term"]` 직접 접근 동일 패턴. tag object에 `term` 키가 없으면 entry 하나 때문에 `collect()` 전체가 `KeyError`로 중단된다. 스타일 부채가 아니라 **가용성 리스크**로 격상해 기록. 공통 정리 라운드에서 `t.get("term")` 방어적 helper로 통합 검토.
- **Coverage 피드 페이지 크기 제약(MTP 10건/TC 20건) → 수집 주기 대비 유실 가능. Clusterer 설계 시 cadence 결정 필요**
