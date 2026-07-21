# Perix Sentinel — Refactoring SDD

> Software Design Document · v0.1
> 목적: **다음 기능(Clusterer, LLM 요약, Scheduler)을 얹기 전에, 현재 코드베이스를 동작 보존(behavior-preserving) 방식으로 정리한다.**
> 기준 커밋: 업로드된 `Perix_Sentinel.zip` 스냅샷 / Python 3.12 / FastAPI 0.115

---

## 0. 한 줄 요약

아키텍처(포트&어댑터)는 그대로 둔다. 리팩터링 대상은 **어댑터 계층의 중복·불일치**와 **조립(wiring)·복원력(resilience)의 부재**에 집중한다. 가장 큰 페이로드는 HTML 컬렉터 5개에 흩어진 보일러플레이트와, 소스마다 제각각인 날짜·태그 처리의 통일이다.

---

## 1. 목표 (Goals)

1. **중복 제거** — HTTP 호출, 날짜 파싱, 태그 생성의 반복 코드를 공통 모듈로 추출
2. **일관성 확보** — HTTP 라이브러리, datetime(timezone), 태깅 규칙을 하나로 통일
3. **복원력 추가** — 컬렉터 1개가 실패해도 전체 수집이 죽지 않도록 격리
4. **조립 분리** — 인터페이스 계층(`collect.py`)에 박힌 하드코딩 의존성을 합성 루트(composition root)로 이동
5. **다음 단계 좌석 마련** — Clusterer/LLM이 들어올 자리를 구조적으로 비워두기 (구현은 안 함)

## 2. 비목표 (Non-Goals)

- Clusterer / 시맨틱 중복제거 **구현** (별도 페이즈)
- LLM 한국어 요약 **구현** (별도 페이즈)
- APScheduler 도입 (별도 페이즈)
- **스코어링 가중치 재보정** — 이건 동작 변경이므로 리팩터링이 아니라 별도 작업으로 분리
- DB 스키마의 의미 변경 (마이그레이션 호환 유지)

> **원칙: 이 SDD의 모든 변경은 "입력이 같으면 출력이 같다"를 지킨다.** 동작이 바뀌는 항목은 전부 Non-Goal로 빼서 별도 PR로 다룬다.

---

## 3. 현재 상태 (As-Is) 요약

```
app/
  domain/        models(CollectedItem) · ports(3) · services(scoring, briefing)
  application/   use_cases(CollectTrends)
  infrastructure/ collectors(7) · publishers(Discord) · repositories(SQLite)
  interface/     api(collect, items, health)
  core/          config · logger
```

레이어 경계는 깨끗함. 문제는 **infrastructure 내부**와 **계층 간 조립**에 있음.

---

## 4. 리팩터링 대상 (Refactoring Targets)

우선순위: **P1(즉시·고효과)** → **P2(중요)** → **P3(여유 될 때)**

### R1. HTTP 호출 보일러플레이트 중복 — P1
**증상**: `anthropic / deepmind / meta / mistral / github` 컬렉터가 아래를 거의 동일하게 반복.
```python
async with httpx.AsyncClient(follow_redirects=True, timeout=15~20,
                             headers={"User-Agent": "Mozilla/5.0"}) as client:
    response = await client.get(URL)
    response.raise_for_status()
soup = BeautifulSoup(response.text, "html.parser")
```
**문제**: 타임아웃 값 제각각, 재시도·백오프 없음, UA 하드코딩 분산.
**처방**: `infrastructure/http/async_client.py`에 `fetch_html(url) -> BeautifulSoup` 와 `fetch_json(url) -> dict` 헬퍼. 타임아웃·UA·재시도를 한 곳에서 관리.

### R2. HTTP 라이브러리 불일치 — P1
**증상**: 대부분 `httpx`(async)인데 `huggingface_api_collector`만 `requests`(sync) + `asyncio.to_thread`. 게다가 **`requests`가 `requirements.txt`에 없음** (선언 안 된 의존성).
**처방**: HF 컬렉터를 `httpx` 비동기로 통일하고 R1 헬퍼 사용. `requests` 제거.

### R3. 날짜 파싱 분산 + timezone 불일치 — P1
**증상**: 컬렉터마다 `_parse_date`/`_extract_date`가 따로 존재. 폴백이 `datetime.utcnow()`(naive)와 `datetime.now(timezone.utc)`(aware)로 **섞여 있음**.
**문제**: ① Python 3.12에서 `datetime.utcnow()` deprecated. ② **24시간 윈도우 기능이 timestamp 정확도에 직접 의존** → naive/aware 혼용은 비교 버그의 씨앗.
**처방**: `core/datetime.py`에 `parse_date(raw, formats) -> datetime(aware, UTC)` + `now_utc()`. 전 컬렉터를 **timezone-aware UTC로 통일**. `published_at`은 항상 aware.

### R4. 태그 생성 로직 중복 — P2
**증상**: `meta / mistral / github / huggingface`가 각자 `KEYWORD_TAGS` 사전과 `_build_tags`를 보유. 규칙이 소스마다 다르고 키워드도 중복.
**처방**: `domain/services/tagger.py`로 통합. 소스별 고정 태그 + 공통 키워드 매핑을 한 곳에서. (스코어링 키워드와 출처가 겹치므로 정책 일원화 효과도 있음)

### R5. 컬렉터 실패 격리 부재 — P1
**증상**: `collect.py`가 컬렉터를 순차 루프로 돌리는데, `raise_for_status()`가 던지면 **그 시점에 루프 전체가 중단**됨. 한 소스의 5xx가 나머지 6개를 못 돌게 함.
**처방**: 컬렉터별 `try/except`로 격리하고 결과를 값 객체로 수집.
```python
@dataclass
class CollectorResult:
    source: str
    items: list[CollectedItem]
    error: str | None
    duration_ms: int
```
→ 모니터링(Aegis) 단계의 입력으로도 재사용 가능.

### R6. 합성 루트(Composition Root) 부재 — P2
**증상**: `interface/api/collect.py`가 컬렉터 7개·publisher·repository를 직접 `import`하고 `new` 함. `main.py`도 repository를 따로 인스턴스화. 인터페이스 계층이 인프라 구체 타입을 알고 있음 → **의존 방향 역전 위반에 가까움**.
**처방**: `app/bootstrap.py`(또는 `composition.py`)에 팩토리. 인터페이스는 use case만 호출하고, 구체 어댑터 선택은 합성 루트가 담당.

### R7. 수집 직렬 실행 — P2
**증상**: `collect.py`가 컬렉터를 `for`로 순차 실행 → 7개면 7배 시간.
**처방**: R5의 격리와 함께 `asyncio.gather`로 병렬화. (단, 외부 사이트 부하 고려해 동시성 상한 둘 것)

### R8. Repository 인스턴스/커넥션 관리 — P3
**증상**: 메서드마다 `aiosqlite.connect()`를 새로 염. 요청마다 `SqliteItemRepository()` 새로 생성.
**처방**: 단일 인스턴스 + 커넥션 수명 관리(혹은 경량 풀). MVP 규모에선 성능 문제 아님 → **P3**, 단 합성 루트(R6) 정리 시 자연스럽게 같이.

### R9. 수집량 무제한 — P2
**증상**: `openai_rss_collector`가 피드 전체를 반환 → DB에 OpenAI 960건. 컬렉터에 상한/윈도우 없음.
**처방**: 정규화 단계에서 **24h 윈도우 필터**와 소스별 `max_items` 적용. (이건 동작 변경에 가까우므로, 필터를 "끌 수 있는 옵션"으로 넣어 기존 동작과 호환 유지)

### R10. `CollectedItem` 책임 과다 — P3 (다음 페이즈 좌석)
**증상**: 하나의 dataclass가 (a) 컬렉터 출력 DTO, (b) 영속 모델, (c) 스코어링 결과(score/importance/reason/is_briefed)를 전부 담음.
**문제**: 곧 들어올 **Clusterer/Event 모델**과 충돌. "여러 기사 → 하나의 사건"을 표현하려면 분리가 필요.
**처방(이번엔 설계만)**: 경계를 문서화만 하고, 분리는 Clusterer 페이즈에서. 지금은 R10을 "알려진 부채"로 등록.

### R11. 테스트 부재 — P1 (선행)
**증상**: `tests/`에 `__init__.py`만 있음.
**문제**: 테스트 없이 R1~R9를 건드리면 회귀를 못 잡음.
**처방**: 리팩터링 **착수 전에** 특성화 테스트(characterization test) 확보.

---

## 5. 목표 구조 (To-Be)

추가/이동되는 모듈만 표기 (기존 레이어는 유지):

```
app/
  core/
    datetime.py        # R3: parse_date(), now_utc()
  infrastructure/
    http/
      async_client.py  # R1/R2: fetch_html(), fetch_json()
    collectors/
      base.py          # R1: BaseHtmlCollector (템플릿 메서드)
      ... (기존 7개, base 상속으로 슬림화)
  domain/
    services/
      tagger.py        # R4: 태그 생성 일원화
    models/
      collector_result.py  # R5: CollectorResult 값 객체
  bootstrap.py         # R6: 합성 루트 (어댑터 조립)
```

### 컬렉터 템플릿 메서드 (R1 핵심)
```python
class BaseHtmlCollector(CollectorPort):
    source: str
    url: str

    async def collect(self) -> list[CollectedItem]:
        soup = await fetch_html(self.url)      # 공통
        return self.parse(soup)                # 소스별로만 구현

    def parse(self, soup) -> list[CollectedItem]: ...
```
→ 각 컬렉터는 **`parse()`만** 남고, HTTP/로깅/예외는 베이스가 처리. 코드량 대폭 감소.

---

## 6. 마이그레이션 계획 (Phased)

각 페이즈는 독립 PR. **앞 페이즈가 그린 상태에서만 다음 진행.**

| Phase | 내용 | 대상 | 리스크 |
|---|---|---|---|
| **P0** | 특성화 테스트 확보 (scoring + 컬렉터 1개 골든파일) | R11 | 낮음 |
| **P1** | `http/async_client` + `core/datetime` 추출, 전 컬렉터 적용 | R1·R2·R3 | 중 (전 컬렉터 수정) |
| **P2** | `BaseHtmlCollector` 도입, 컬렉터 슬림화 | R1 | 중 |
| **P3** | `tagger` 통합 | R4 | 낮음 |
| **P4** | `CollectorResult` + 실패 격리 + `gather` 병렬화 | R5·R7 | 중 |
| **P5** | `bootstrap` 합성 루트, repository 정리 | R6·R8 | 중 |
| **P6** | 정규화 24h 윈도우/상한 (옵션 플래그) | R9 | 중 (동작 인접) |

> R10(모델 분리)은 리팩터링이 아니라 **Clusterer 페이즈의 선행 설계**로 넘김.

---

## 7. 테스트 전략

- **특성화 테스트 우선(P0)**: 현재 `calculate_score`의 입력→출력을 그대로 고정. 리팩터링 후에도 동일 점수가 나오는지 검증.
- **골든파일**: 컬렉터별로 실제 HTML 응답을 1개씩 저장(fixture) → 네트워크 없이 `parse()` 회귀 테스트. (죽은 컬렉터 진단에도 그대로 재사용)
- **날짜 파서 단위 테스트(R3)**: 소스별 실제 날짜 문자열 샘플 → aware UTC 변환 검증.
- 도구: 이미 `pytest`, `pytest-asyncio`가 `requirements.txt`에 있음 → 추가 설치 불필요.

---

## 8. 리스크 & 롤백

- **최대 리스크**: P1에서 전 컬렉터를 동시에 수정 → 회귀 위험. **완화**: P0 테스트를 먼저 깔고, 컬렉터를 한 개씩 베이스로 이전하며 그린 확인.
- **timezone 전환(R3)**: 기존 DB에 저장된 naive 문자열과 비교 시 주의. **완화**: 읽을 때 aware로 승격하는 어댑터 한 줄 추가.
- **롤백 단위**: 페이즈별 PR이라 문제 시 해당 PR만 revert.

---

## 9. 완료 정의 (Definition of Done)

- [ ] 모든 컬렉터가 `BaseHtmlCollector`/공통 HTTP·날짜 모듈 사용
- [ ] `datetime.utcnow()` 0건, `published_at` 전부 aware UTC
- [ ] 컬렉터 1개 실패가 나머지에 영향 없음 (격리 테스트 통과)
- [ ] 인터페이스 계층에서 인프라 구체 타입 직접 import 0건 (합성 루트 경유)
- [ ] 특성화 테스트로 스코어링 동작 불변 증명
- [ ] `requirements.txt`와 실제 import 일치 (`requests` 등 정리)

---

## 10. 다음 페이즈 연결 (이 리팩터링이 깔아주는 길)

| 다음 기능 | 이번 리팩터링이 만든 좌석 |
|---|---|
| Clusterer / Event | R10 부채 등록 → 모델 분리 설계 착수 지점 명확화 |
| LLM 한국어 요약 | `get_unsummarized()` 훅 + 합성 루트(R6)로 summarizer 어댑터 주입 자리 |
| Scheduler | `CollectorResult`(R5) → 스케줄 실행 결과 리포팅 그대로 사용 |
| Aegis 모니터링 | `CollectorResult`의 error/duration → 헬스 신호 소스 |
