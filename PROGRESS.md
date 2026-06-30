# PROGRESS — Perix Sentinel Refactoring + Collector Revival

기준 문서: `docs/SDD/Perix_Sentinel_Refactoring_SDD.md` / `docs/SDD/Perix_Sentinel_Collector_Revival_SDD.md`
원칙: 모든 변경은 "입력 같으면 출력 같다"(behavior-preserving). 동작 변경은 Non-Goal.

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
  - **37 passed** (P1 완료 시점)

### Collector Revival SDD
- **D0 — 진단** ✅ (2026-07-01)
  - 결과: GitHub(19건)·HuggingFace(10건)·DeepMind(24건)·Meta(10건) — 이미 정상 동작
  - **Mistral 0건** → **F3**: Next.js → Astro 프레임워크 전환으로 `__next_f` 임베디드 JSON 소멸
- **D3 — Mistral 파서 재작성 (F3 수리)** ✅
  - 구: Next.js `__next_f` push 스크립트 파싱 (동작 불가)
  - 신: `article[data-title]` 75개, `footer p` 날짜 ("June 23, 2026"), `h2` 제목, content `p` 설명
  - 날짜 포맷 `"%B %d, %Y"` → aware UTC 정상 파싱
  - Live 검증: 75건 수집 확인
- **D5 — Mistral 골든 fixture 테스트** ✅
  - `tests/fixtures/mistral_news.html` (444KB) + `mistral_news.golden.json` (75건)
  - `tests/test_mistral_collector_golden.py`: 5개 테스트 (golden match · aware UTC · mistral 태그 · URL 중복 없음)
  - **42 passed**

## 진행 중인 것
- (없음)

## 다음 단계
- **P2 (Refactoring SDD)** — `BaseHtmlCollector` 도입, HTML 컬렉터 5개 슬림화
  - 전제: 모든 컬렉터가 `fetch_html` + `parse(soup)` 구조로 확정됨 (✅)
  - 대상: Anthropic, DeepMind, GitHub, Meta, Mistral
- **arXiv / Hacker News 컬렉터 추가** (Collector Revival SDD §11)
  - 둘 다 공식 API 기반 → 스크래핑 리스크 없음
  - 선행 조건: 현재 컬렉터 부활 완료 (✅)

## 미결 결정사항
- **P2 범위 확정**: `BaseHtmlCollector`로 슬림화할 컬렉터 목록과 `parse()` 시그니처 합의 필요
- **arXiv·HN 착수 시점**: Collector Revival SDD는 완료이나 P2(Refactoring)와 arXiv·HN 추가 중 우선순위 사용자 결정 필요
- **Mistral F3 결정 근거 기록**: Next.js→Astro 전환. 새 구조(정적 HTML)가 임베디드 JSON보다 안정적이므로 headless 없이 해결. PROGRESS에 기록 완료.
- **진행 방식(합의됨)**: 페이즈마다 멈춰서 확인. 그린이어도 자동 다음 페이즈 진행하지 않음.
