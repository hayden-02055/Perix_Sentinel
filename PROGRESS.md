# PROGRESS — Perix Sentinel Refactoring + Collector Revival

기준 문서: `docs/SDD/Perix_Sentinel_Refactoring_SDD.md` / `docs/SDD/Perix_Sentinel_Collector_Revival_SDD.md` / `docs/SDD/Perix_Sentinel_Test_Infra_Mistral_Wrapup_SDD.md`

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
- **P2 (Refactoring SDD)** — `BaseHtmlCollector` 도입, HTML 컬렉터 5개 슬림화
  - 전제: 모든 HTML 컬렉터가 `fetch_html` + `parse(soup)` 구조로 확정됨 (✅)
- **arXiv / Hacker News 컬렉터 추가** (Collector Revival SDD §11)
  - 공식 API 기반 → 스크래핑 리스크 없음

## 미결 결정사항
- **`_recency_score` 정책**: DB에 저장된 구형 naive datetime 문자열 읽기 시 aware 승격 어댑터(SDD R3 §8 완화책) 미구현. 현재 신규 수집 아이템은 모두 aware라 문제 없으나, DB 기존 행 재처리 시 주의 필요.
- **Silent date fallback 가시화 (③ 공통 부채)**: `parse_date()`가 파싱 실패 시 `now_utc()`로 조용히 fallback. 소스마다 개별 수정 대신 **공통 경고 로그 레이어 추가**로 한 번에 해결 예정. P2 또는 전반 정리 라운드에서.
- **P2 범위**: `BaseHtmlCollector` 상속 대상 확정 필요 (Anthropic, DeepMind, GitHub, Meta, Mistral 후보)
- **arXiv·HN 착수 시점**: P2 전/후 사용자 결정 필요
- **진행 방식(합의됨)**: 페이즈마다 멈춰서 확인. 그린이어도 자동 다음 페이즈 진행하지 않음.
