# PROGRESS — Perix Sentinel Refactoring

기준 문서: `docs/SDD/Perix_Sentinel_Refactoring_SDD.md`
원칙: 모든 변경은 "입력 같으면 출력 같다"(behavior-preserving). 동작 변경은 Non-Goal.

## 완료된 것
- **P0 — 특성화 테스트 확보 (R11)** ✅ `refactor/p0-characterization-tests`
  - `tests/conftest.py`: `mock_http` fixture. `httpx.AsyncClient`를 httpx 모듈 레벨에서 패치 → P1/P2에서 공통 HTTP 클라이언트로 옮겨도 테스트 그대로 유효.
  - `tests/test_scoring_characterization.py`: `calculate_score`/`apply_score` 입출력 5케이스 + importance 임계값 고정. (스코어링 동작 불변 증명용 — DoD 항목)
  - `tests/test_anthropic_collector_golden.py` + `tests/fixtures/anthropic_news.html`(실제 응답) + `anthropic_news.golden.json`: Anthropic `collect()` 파싱 결과 골든 스냅샷. 네트워크 없이 회귀 검증.
  - `published_at`은 `tzinfo` 벗긴 instant로 비교 → R3(aware UTC 전환) 후에도 그린 유지하도록 설계.
  - `pytest.ini` 추가 (asyncio_mode=auto). **14 passed.**

## 진행 중인 것
- (없음) P0 완료, P1 착수 대기 중.

## 다음 단계
- **P1 — R1·R2·R3** (사용자 확인 후 착수):
  - `infrastructure/http/async_client.py`: `fetch_html(url)->BeautifulSoup`, `fetch_json(url)->dict`. 타임아웃·UA·재시도 일원화.
  - `core/datetime.py`: `parse_date(raw, formats)->aware UTC datetime`, `now_utc()`.
  - 전 컬렉터를 위 두 모듈로 전환. HF 컬렉터 `requests`→`httpx`(R2), `requirements.txt`에서 `requests` 정리.
  - 각 컬렉터 전환마다 `pytest` 그린 확인.

## 미결 정의사항
- 골든파일 범위: 현재 Anthropic 1개만. 나머지 6개 컬렉터 골든파일은 P2(BaseHtmlCollector) 진입 전 추가 권장 — 단 SDD P0는 "1개"만 요구하므로 일단 보류.
- 진행 방식(합의됨): **페이즈마다 멈춰서 확인**. 그린이어도 자동으로 다음 페이즈 진행하지 않음.
- 세션 범위(합의됨): 이번 세션 목표 = P0 + P1.
- Python 실제 버전 3.13 (SDD는 3.12 기준) — `datetime.utcnow()` deprecated 경고는 R3에서 제거 예정.
