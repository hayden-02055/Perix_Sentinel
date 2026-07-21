# Perix Sentinel — Clusterer + Event 모델 SDD

> Software Design Document · v0.1
> 목적: **origin 사건과 coverage 메아리를 매칭해 `Event`(사건)를 생성하고, 브리핑 단위를 item → Event로 전환한다.**
> 선행: Tier1 origin 11개 + Tier2 coverage 2개(TechCrunch·MarkTechPost) 적재 중. store-only 배선 완료.
> 후속: 스코어링 재보정(값 튜닝), 나머지 coverage 3개, LLM 한국어 요약.

---

## 0. 한 줄 요약

**Clusterer를 수집 파이프라인 안이 아니라 별도 배치 패스로 만든다.** coverage 메아리는 origin보다 **나중에** 도착하므로, 수집 시점에 클러스터링하면 corroboration은 언제나 0이다. 따라서 파이프라인을 **2-Phase(수집 / 분석)로 분리**하고, 분석 단계에서 **개체명+시간창(주) + 제목 유사도(보조)**로 매칭해 `Event`를 만든 뒤, **KST 08:00에 Top-5만 브리핑**한다. 이 과정에서 `publisher=None` 트릭은 구조적으로 불필요해져 은퇴한다. **신규 외부 의존성 0.**

---

## 1. 맥락: 무엇이 바뀌는가

### 1.1 현재 (Phase 분리 전)

```
collector.collect() → dedup(url_hash) → apply_score → save → score>=15 → publish
```
컬렉터 1개당 1회, 스트리밍. **corroboration 개념이 들어갈 자리가 없다.**

### 1.2 시간차 문제 (이 SDD의 존재 이유)

```
화 09:00  OpenAI 발표          ← origin 수집
화 14:00  TechCrunch 속보      ← echo 1 (5h 뒤)
수 02:00  MarkTechPost 요약    ← echo 2 (17h 뒤)
```
origin 수집 시점에 echo는 **아직 세상에 없다.** 인라인 클러스터링은 원리적으로 불가능.

### 1.3 목표 구조 (2-Phase)

```
[Phase 1 — 수집]  (1~3h 주기)
  origin   → dedup → 저장
  coverage → dedup → 저장          ※ 브리핑 관 진입 없음

[Phase 2 — 분석]  (KST 08:00, 1일 1회)
  get_unbriefed_since(48h)
    → Clusterer          : origin ↔ coverage 매칭 → Event 생성
    → Scoring            : corroboration + diversity
    → Top-K(5) + 바닥점수
    → BriefingGenerator  : Event 단위 렌더링
    → Publisher          : Discord 1회 발행
    → mark_briefed
```

### 1.4 확정된 전제 (선행 논의 결과 — 재논의 대상 아님)

| # | 전제 |
|---|---|
| 1 | 브리핑: **KST 08:00, 1일 1회**. `BRIEFING_TZ=Asia/Seoul` |
| 2 | lookback **48h** + `is_briefed` 가드 → 미달 항목은 다음 날 자동 재평가 (별도 maturity 임계값 불필요) |
| 3 | 선별: **Top-K(K=5) + 최소 바닥점수**. 고정 threshold 방식 폐기 |
| 4 | 브리핑 단위: **Event** |
| 5 | Event **영속화**. **aggregate 형태**(members 내포), `event_id: str` |
| 6 | 매칭: **C(개체명+시간창) 주 + B(제목 유사도) 보조** |
| 7 | 저장소: SQLite 유지. 포트 분리로 Mongo 대비만 (어댑터는 만들지 않음) |

---

## 2. 핵심 설계 — 매칭 알고리즘

### 2.1 왜 C(개체명)인가

AI 생태계의 사건은 대부분 **`{조직} + {모델·제품명}`**으로 특정된다.

```
origin  : "Introducing GPT-5.5 agents"                    (OpenAI 블로그)
echo    : "OpenAI launches GPT-5.5 with agentic tooling"  (TechCrunch)
echo    : "OpenAI Releases GPT-5.5: A Technical Overview"  (MarkTechPost)
```

제목 문자열은 크게 다르지만 **`{OpenAI, GPT-5.5}`는 공통**이다. 반대로 제목 유사도(B) 단독은 매체별 톤 차이("Why X matters" 류 에디토리얼)에 취약하다. 그래서 **C를 게이트로, B를 타이브레이커로** 쓴다.

### 2.2 개체 추출 (신규 의존성 0)

NER 라이브러리를 쓰지 않는다. 이 도메인은 **닫힌 사전 + 단순 패턴**으로 충분하다.

**(a) 조직 사전** — origin 소스 목록이 그대로 사전이 된다
```python
_ORG_ALIASES = {
    "openai": {"openai"},
    "anthropic": {"anthropic", "claude"},
    "google": {"google", "deepmind", "google deepmind", "gemini"},
    "meta": {"meta", "meta ai", "facebook"},
    "mistral": {"mistral", "mistral ai"},
    "nvidia": {"nvidia"},
    "huggingface": {"huggingface", "hugging face"},
    "deepseek": {"deepseek"},
    "alibaba": {"alibaba", "qwen"},
    "moonshot": {"moonshot", "kimi"},
    "zhipu": {"zhipu", "glm", "zai"},
    # 확장 여지: xai, cohere, microsoft, apple, amazon, ibm, stability
}
```
> 조직명이 곧 모델 브랜드인 경우(`claude`, `gemini`, `qwen`)를 별칭에 포함시켜 재현율을 올린다.

**(b) 모델·제품 패턴** — 버전 토큰
```python
_MODEL_RE = re.compile(r"\b([A-Z][A-Za-z]{1,15})[-\s]?(\d+(?:\.\d+)?)\b")
# GPT-5.5 / Llama 4 / Gemini 2.5 / Claude 4.5 / Qwen3 → ("gpt","5.5") 형태로 정규화
```

**(c) 정규화 규칙**
- 소문자화, 하이픈·공백 통일 → `GPT-5.5` == `GPT 5.5` == `gpt5.5`
- 추출 결과: `entities = {"org": {...}, "model": {...}}`

> ⚠️ 이 정규식은 **A0에서 실데이터로 정밀도 확인 필수**(§8). 오탐 예: "Top 10 Tools", "Q4 2026".

### 2.3 매칭 규칙 — 3단계 게이트

coverage 항목 하나가 들어오면, 후보 origin 항목들에 대해 순서대로 적용한다.

**게이트 1 — 시간창**
```
origin.published_at - 6h  ≤  coverage.published_at  ≤  origin.published_at + 48h
```
- `+48h`: 메아리가 도착하는 정상 범위
- `-6h`: coverage가 **먼저** 나오는 경우 대비 (엠바고 해제 시차, 유출 보도, 소스 타임스탬프 오차). 이 여유가 없으면 정상 매칭을 놓친다.

**게이트 2 — 개체 일치**
```
조직 교집합 ≥ 1  AND  ( 모델 교집합 ≥ 1  OR  게이트1 통과 origin 후보가 유일 )
```
- 조직만 겹치는 건 약하다("OpenAI"는 하루에도 여러 사건에 등장). 모델명까지 겹쳐야 확신.
- 단, 시간창 안에 해당 조직 origin이 하나뿐이면 모델명 없이도 인정 (재현율 확보).

**게이트 3 — 타이브레이커 (B 보조)**
게이트 2를 통과한 origin이 2개 이상이면, **제목 토큰 Jaccard 유사도 최고점** 하나를 선택.
```python
tokens(title) = 소문자화 → 불용어 제거 → 알파벳/숫자만 → set
jaccard(a, b) = |a ∩ b| / |a ∪ b|
```
동점이면 `published_at`이 coverage와 더 가까운 origin.

### 2.4 결정: coverage 1건 → Event 1개 (최선 매칭만)

한 기사가 여러 사건을 다루는 경우(주간 요약 기사 등)가 있지만, **다중 배정은 `echo_count`를 부풀려 `diversity` 신호를 왜곡**한다. MVP는 **최선 매칭 1개에만 귀속**시키고, 어디에도 못 붙은 coverage는 그대로 미귀속 상태로 남긴다(폐기 아님).

### 2.5 결정: origin ↔ origin은 묶지 않는다

PROGRESS.md에 "DeepMind(`deepmind.google`) vs Google Research(`research.google`) 의미 중복"이 미결로 있다. 하지만 origin 병합은 **"둘 중 어느 쪽이 대표 사건인가"**라는 별개의 판단을 요구한다. 이 SDD에서는 **origin 1건 = Event 1개**로 고정하고, origin 병합은 이월한다.

### 2.6 boilerplate 정제 (선행 논의 반영)

MarkTechPost `summary` 말미에 모든 항목 공통 문자열(`The post ... appeared first on MarkTechPost.` + `<a>` 링크)이 붙는다. **매칭에 `summary`를 쓰지 않고 `title`만 쓰면 이 문제는 자동 회피**된다.
- **결정: 매칭 입력은 `title`로 한정**한다. `summary`는 브리핑 렌더링에만 사용.
- 부수 효과: 계산량 감소, 소스별 본문 형식 차이의 영향 제거.

---

## 3. 목표 (Goals)

1. `Event` 도메인 모델 + `EventRepositoryPort` + SQLite 어댑터.
2. `clusterer.py`를 **순수 도메인 서비스**로 구현 (I/O 없음, `list[CollectedItem] → list[Event]`).
3. `ItemRepositoryPort.get_unbriefed_since(since)` 추가.
4. `DailyBriefingUseCase` 신설 — Phase 2 전체 조립.
5. `CollectTrendsUseCase`에서 **브리핑 책임 제거** (수집 전담).
6. `BriefingGenerator`를 Event 단위로 전환, **1회 1메시지 digest**.
7. `POST /briefing/run` 수동 트리거 엔드포인트.
8. 스케줄러로 KST 08:00 자동 실행.
9. 골든 테스트: 매칭 정확도 + Top-K 선별 + 중복 브리핑 방지.

---

## 4. 비목표 (Non-Goals)

- **LLM 한국어 요약** — 계속 보류. `BriefingGenerator`는 문자열 조립 유지.
- **origin ↔ origin 병합** (§2.5).
- **Mongo 어댑터 구현** — 포트 분리까지만. 어댑터는 배포 단계.
- **`ItemRepositoryPort`의 `int` → `str` ID 전면 전환** — 신규 Event만 `str`. 기존은 부채 기록.
- **스코어링 가중치 값 튜닝** — corroboration/diversity가 **들어갈 구조**만 만든다. 실제 값 조정은 MVP 가동 후 실데이터 기준.
- **나머지 coverage 3개**(MIT TR·Verge·Decoder) — 별도 SDD.
- **다중 Event 귀속** (§2.4).

---

## 5. Event 모델 & 스키마

### 5.1 도메인 모델

```python
@dataclass
class EventMember:
    item_id: str
    role: str                 # "origin" | "echo"
    source: str               # "TechCrunch"
    title: str
    url: str
    published_at: datetime

@dataclass
class Event:
    title: str                            # origin item 제목 승계
    occurred_at: datetime                 # origin.published_at
    members: list[EventMember] = field(default_factory=list)
    entities: dict = field(default_factory=dict)   # {"org": [...], "model": [...]}
    echo_count: int = 0                   # role=="echo" 개수
    diversity: int = 0                    # echo의 고유 source 종류 수
    score: int = 0
    importance: str = "normal"
    is_briefed: bool = False
    briefed_at: datetime | None = None
    event_id: str = ""                    # ← str (Mongo 대비)
```

> `EventMember`에 `source`/`title`/`url`을 **의도적으로 비정규화**한다. 브리핑 렌더링 시 item 테이블 재조회가 불필요해지고, 그대로 Mongo embedded document가 된다.

### 5.2 SQLite 스키마 (기존 JSON 컬럼 패턴 답습)

```sql
CREATE TABLE IF NOT EXISTS events (
    event_id     TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    occurred_at  TEXT NOT NULL,      -- ISO8601 aware UTC
    members      TEXT NOT NULL,      -- JSON array  ← 조인 테이블 대신
    entities     TEXT NOT NULL,      -- JSON object
    echo_count   INTEGER DEFAULT 0,
    diversity    INTEGER DEFAULT 0,
    score        INTEGER DEFAULT 0,
    importance   TEXT DEFAULT 'normal',
    is_briefed   INTEGER DEFAULT 0,
    briefed_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_briefed  ON events(is_briefed);
```

`members`/`entities`를 JSON 컬럼으로 두는 것은 `collected_items.tags`·`metadata`가 이미 쓰는 방식이라 **신규 패턴이 아니다.**

### 5.3 `event_id` 생성

```python
event_id = hashlib.md5(f"{origin_item.url_hash}".encode()).hexdigest()
```
origin 1건 = Event 1개(§2.5)이므로 origin의 `url_hash`가 곧 안정적 식별자. **재실행해도 같은 Event id가 나와 멱등성이 보장**된다(같은 사건이 매일 새 Event로 중복 생성되지 않음).

---

## 6. 스코어링 변경 (구조만, 값은 이월)

```python
event.score = origin_item.score \
            + CORROBORATION_WEIGHT * event.echo_count \
            + DIVERSITY_WEIGHT     * event.diversity
```

- 두 상수는 `scoring_policies.py`에 신규 추가. **초기값은 잠정**(예: 각 5, 3)이며 MVP 가동 후 조정.
- `BRIEFING_THRESHOLD(15)`는 **Top-K + 바닥점수로 대체**:
  ```python
  TOP_K = 5
  MIN_SCORE_FLOOR = 10      # 조용한 날 억지로 5개 채우지 않음
  ```
- 기존 `apply_score(item)`는 **그대로 둔다.** item 점수는 Event 점수의 입력이 된다(파괴적 변경 없음).

> 이 SDD는 스코어링 **파일을 수정한다.** 지금까지 "스코어링 무수정" 원칙을 지켜왔으나, 그 원칙의 목적("Tier2가 배선되기 전엔 튜닝하지 말 것")이 **이번 작업으로 충족**된다. 다만 **가중치 값 튜닝은 여전히 비목표**(§4)이며, 이번엔 corroboration이 흘러들어갈 **경로만** 만든다.

---

## 7. 파이프라인 재배선

### 7.1 `CollectTrendsUseCase` — 브리핑 책임 제거

```python
# 제거: apply_score 이후의 briefable / publisher.publish / mark_briefed 블록
# 유지: collect → exists_by_hash → apply_score → save
```
결과:
- `publisher` 파라미터 자체가 불필요 → **`publisher=None` 트릭 은퇴**
- `/collect`와 `/collect/coverage`의 차이는 **컬렉터 목록뿐**이 되어, store-only 불변식이 "특수 배선"이 아니라 **기본 동작**이 된다

### 7.2 `DailyBriefingUseCase` (신규)

```python
class DailyBriefingUseCase:
    async def execute(self) -> dict:
        since  = now_utc() - timedelta(hours=LOOKBACK_HOURS)   # 48
        items  = await self._items.get_unbriefed_since(since)
        events = cluster(items)                                 # 순수 함수
        for e in events:
            score_event(e)
            await self._events.upsert(e)                        # 멱등
        selected = select_top_k(events, k=TOP_K, floor=MIN_SCORE_FLOOR)
        if selected:
            await self._publisher.publish(render_digest(selected))
            for e in selected:
                await self._events.mark_briefed(e.event_id)
                for m in e.members:
                    await self._items.mark_briefed(m.item_id)   # 재평가 대상에서 제외
        return {...}
```

> `is_briefed`를 **Event와 item 양쪽에 기록**한다. item 쪽은 `get_unbriefed_since` 필터가 소비하고, Event 쪽은 중복 발행 방지가 소비한다.

### 7.3 브리핑 출력 형식

```
[Perix Sentinel · 2026-07-22 08:00 KST]

1. OpenAI, GPT-5.5 에이전트 API 공개
   origin : OpenAI Blog
   echo   : TechCrunch, MarkTechPost (2)
   score  : 34 (critical)
   https://openai.com/...

2. Mistral, Codestral 2 오픈웨이트 공개
   ...
```
**Discord 1회 1메시지.** 항목별 개별 메시지 금지(일 1회 digest 성격에 배치).

### 7.4 스케줄러

| 잡 | 주기 | 대상 |
|---|---|---|
| 수집 | 1~3h | `/collect` + `/collect/coverage` |
| 브리핑 | **매일 08:00 KST** | `DailyBriefingUseCase` |

- APScheduler(단일 프로세스) 또는 cron→엔드포인트 호출. **A0에서 배포 형태(Docker) 확인 후 택일.**
- `config.py`에 `BRIEFING_TZ="Asia/Seoul"`, `BRIEFING_HOUR=8` 추가.
- **저장은 UTC, 스케줄·표시만 KST.** 내부 datetime 정책(aware UTC) 불변.

---

## 8. 절차 (A0 ~ A4)

| 단계 | 내용 |
|---|---|
| **A0 관측** | **최우선.** 아래 4가지 실데이터 확인 → `docs/notes` 기록 |
| **A1 모델** | `Event`·`EventMember`, `EventRepositoryPort`, SQLite 어댑터, 스키마 마이그레이션 |
| **A2 로직** | `clusterer.py` 순수 함수 (개체 추출 + 3게이트). **여기서 멈추고 골든 테스트로 검증** |
| **A3 배선** | `get_unbriefed_since` 추가 → `DailyBriefingUseCase` → `CollectTrendsUseCase` 브리핑 제거 → `POST /briefing/run` |
| **A4 실가동** | 수동 트리거로 실행 → Event 생성·Top-5 선별·Discord 1회 발행 확인 → 스케줄러 등록 |

### A0 확인 항목 (4가지)

1. **ground truth 존재 여부 (가장 중요)**
   현재 DB의 coverage 30건(TechCrunch 20 + MarkTechPost 10)이 **실제로 origin 항목과 대응하는가?** origin 다수가 과거 백필분(OpenAI 1037건 등)이라, **48h 창 안에 매칭 가능한 쌍이 0일 가능성**이 있다. 0이면 클러스터러를 검증할 방법이 없으므로, **먼저 origin+coverage를 동시에 며칠 수집해 실데이터를 확보**한 뒤 A2로 진행한다.
   → 손으로 매칭되는 사건 쌍을 **최소 3개** 찾아 골든 테스트의 정답으로 삼는다.

2. **개체 추출 정밀도** — §2.2 정규식을 실제 제목 100건에 돌려 오탐/미탐 확인. 오탐률이 높으면 패턴 축소 또는 사전 우선 방식으로 전환.

3. **시간창 타당성** — 실제 매칭 쌍의 origin↔echo 시차 분포 측정. `+48h`가 과대/과소인지 판단.

4. **배포 형태 확인** — Docker 단일 컨테이너인지에 따라 스케줄러 방식 결정(§7.4).

---

## 9. 테스트 계획

기존 골든 패턴(`test_*_collector_golden.py`) 준수. **네트워크·DB 없이 실행.**

| 테스트 | 내용 |
|---|---|
| `test_clusterer_golden` | A0에서 확보한 실제 사건 쌍 fixture → 기대 Event 구조와 일치 |
| `test_clusterer_time_window` | 창 밖(+49h, -7h) 항목이 매칭되지 않음 |
| `test_clusterer_entity_gate` | 조직만 겹치고 모델 다름 + 후보 2개 → 매칭 안 됨 |
| `test_clusterer_tiebreak` | 후보 2개 → Jaccard 높은 쪽 선택 |
| `test_clusterer_single_assignment` | coverage 1건이 Event 2개에 중복 귀속되지 않음 (§2.4) |
| `test_event_id_idempotent` | 같은 origin 재클러스터링 시 동일 `event_id` |
| `test_top_k_selection` | 6개 Event 중 5개만, 바닥점수 미달 제외 |
| `test_no_double_briefing` | `is_briefed=1` Event 재발행 안 됨 |
| `test_collect_no_longer_briefs` | `CollectTrendsUseCase` 실행 시 publish 호출 0 (회귀) |

기존 62 passed **전량 유지**가 전제. `CollectTrendsUseCase` 변경으로 깨지는 기존 테스트는 **의도된 변경**이므로 갱신하되, 그 사실을 리뷰 노트에 명시.

---

## 10. Definition of Done

- [ ] **A0 4가지 완료**, 특히 ground truth 3쌍 확보 (없으면 데이터 축적 후 재개)
- [ ] `Event`·`EventMember` 모델, `event_id`가 `str`
- [ ] `events` 테이블 + 인덱스 생성, `members`/`entities` JSON 컬럼
- [ ] `EventRepositoryPort` ABC 분리 (Mongo 어댑터는 만들지 않음)
- [ ] `clusterer.py`가 **순수 함수** — I/O·DB 접근 0
- [ ] 3게이트(시간창 / 개체 / Jaccard 타이브레이커) 구현
- [ ] 매칭 입력이 `title` 한정 (§2.6 boilerplate 회피)
- [ ] `ItemRepositoryPort.get_unbriefed_since()` 추가
- [ ] `DailyBriefingUseCase` 신설, Top-K(5) + 바닥점수 선별
- [ ] `CollectTrendsUseCase`에서 브리핑 로직 제거, `publisher` 의존 해제
- [ ] `/collect/coverage`의 `publisher=None` 특수 배선 제거 확인
- [ ] `BriefingGenerator` Event 단위, **Discord 1회 1메시지**
- [ ] `POST /briefing/run` 수동 트리거
- [ ] `config.py`에 `BRIEFING_TZ`·`BRIEFING_HOUR`·`TOP_K`·`MIN_SCORE_FLOOR`·`LOOKBACK_HOURS` 상수화
- [ ] 스케줄러 등록 (수집 / 브리핑 2종)
- [ ] 신규 테스트 9종 + 기존 62 그린
- [ ] **신규 외부 의존성 0** (스케줄러 제외)
- [ ] `Directory_Structure.md` 갱신 (스켈레톤 시절 문서 → 현행화)
- [ ] PROGRESS.md 기록: 2-Phase 전환 / 스코어링 원칙 해제 사유 / 미결 3건(`int`→`str` ID, Mongo datetime 밀리초, origin 병합)

---

## 부록: 참고 실제 코드

- `app/application/use_cases/collect_trends.py` — 브리핑 로직 이관 대상
- `app/domain/services/scoring_engine.py` / `scoring_policies.py` — 가중치 추가 지점
- `app/domain/services/briefing_generator.py` — Event 단위 전환 대상
- `app/domain/ports/repository.py` — `get_unbriefed_since` 추가, `int` ID 커플링 확인
- `app/infrastructure/repositories/sqlite_item_repository.py` — JSON 컬럼 직렬화 패턴 참고
- `app/interface/api/collect.py` — `_run()` / 엔드포인트 구조
- `tests/test_techcrunch_collector_golden.py` — 골든 테스트 패턴
