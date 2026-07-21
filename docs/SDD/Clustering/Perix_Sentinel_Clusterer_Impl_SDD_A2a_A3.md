# Perix Sentinel — Clusterer 구현 SDD (A2a + A3)

> Software Design Document · v0.2
> 부모: `Perix_Sentinel_Clusterer_Event_SDD.md` (v0.1). 이 문서는 v0.1을 대체하지 않고 **A0 실측 결과로 갱신되는 부분만** 다룬다.
> 선행 완료: A0 관측, A1(Event 모델·EventRepositoryPort·SQLite 어댑터, 66 passed)
> 이 SDD 범위: **A2a**(clusterer 순수 로직) + **A3**(Phase 2 배선·스케줄러)
> 보류: **A2b**(양성 골든 fixture) — 실제 매칭 사건 쌍 자연 발생 대기

---

## 0. 한 줄 요약

A0에서 양성 매칭 쌍은 0개였지만 **사람이 정답을 확인한 실데이터 음성 쌍 5건을 확보**했고, 게이트2가 이를 전부 정확히 걸러냈다. 따라서 A2를 **A2a(로직·음성 검증) / A2b(양성 골든)**로 쪼개 A2a는 지금 진행한다. 동시에 A0에서 드러난 **모델 정규식 오탐 30%**를 화이트리스트 방식으로 교체하고, **HuggingFace 항목의 title이 자연어가 아닌 문제**를 게이트3 예외로 처리한다. A3(Phase 2 배선)는 매칭 품질과 무관하므로 **함께 진행**한다 — 현재 `/collect` 1회 실행에 Discord로 38건이 쏟아지는 문제를 A3가 즉시 해소하기 때문이다.

---

## 1. 맥락 — A0가 바꾼 것

### 1.1 ground truth 재해석 (이 SDD의 출발점)

A0 보고서는 "양성 쌍 0개 → 검증 불가 → A2 보류"로 결론지었다. 그러나 확보된 자산은 다음과 같다:

| 자산 | 성격 | 활용 |
|---|---|---|
| 음성 쌍 5건 | **실데이터** + 사람이 "다른 사건"임을 확인한 정답 | ✅ 골든 테스트의 음성 케이스 |
| 게이트2 실측 결과 | 5건 전부 정확히 탈락시킴 | ✅ 설계가 실데이터로 1회 검증됨 |
| 양성 쌍 | 없음 | ⏸️ A2b로 이월 |

"실데이터 기반 골든 테스트" 원칙은 **파서**에 대한 것이다(피드의 실제 모양을 모르면 파서는 틀린다). clusterer는 **순수 알고리즘**이라 검증 대상이 다르다 — "명세한 게이트가 명세대로 동작하는가". 경계 테스트(+49h 탈락 / +47h 통과)는 도메인 사실의 위조가 아니라 **명세의 검증**이므로 가공 데이터 문제에 해당하지 않는다.

### 1.2 A3를 함께 진행하는 이유

A0 중 `POST /collect` 라이브 실행으로 **Discord에 38건이 일시 발행**됐다.

```
github 18 (47%) · openai 7 · arxiv 6 · huggingface 6 · nvidia 1
```

GitHub Trending이 절반을 차지한 것은 "popularity가 content signal을 압도한다"는 기존 관측의 실채널 재현이다. **A3(Top-5 + 일 1회 digest)가 이 문제의 직접적 해법**이며, 매칭 품질이 완성되지 않아도 효과가 즉시 발생한다. A2b를 기다리며 A3까지 묶어두면 그동안 파이프라인은 계속 38건을 뿜는다.

### 1.3 재개 조건 수정 (A0 결론 일부 정정)

A0는 재개 조건으로 "origin 컬렉터를 Alibaba/Moonshot 등으로 확장"을 제시했다. 그러나 이는 **기존 결정과 충돌**한다 — "중국 랩 개별 스크레이퍼는 fragility만 늘리고 커버리지 이득이 없어 HuggingFace region 태깅으로 흡수한다".

**정정된 재개 조건**: 기존 origin(OpenAI·Anthropic·Google·Meta·Mistral·NVIDIA)의 **메이저 릴리스 자연 발생 대기**. 이들은 월 2~4회 대형 발표를 하고 TechCrunch·MarkTechPost가 반드시 이를 다룬다. A0의 진단("구조적 원인이라 데이터 축적으로 해결 안 됨")은 과하며, **주 원인은 관측 기간이 짧았던 것**이고 커버리지 갭은 부차적이다.

→ **2주 관측 후 A2b 재평가.** 그때까지 `docs/notes`에 관측 로그만 append.

---

## 2. 부모 SDD(v0.1)로부터의 변경점 3건

### 2.1 모델 추출: 정규식 → **화이트리스트** (A0-2 근거)

A0 실측:
- 조직 사전: **22/100 히트** (합리적 재현율)
- 모델 정규식: **10/100 히트, 그중 3건 오탐 → FP 30%**

오탐 사례: `("February","2026")`, `("Scholars","2020")`, `("AutoScout","24")`

**저재현율 + 고오탐이 동시 발생**한 것은 가드를 덧붙일 문제가 아니라 접근법이 도메인과 맞지 않는다는 신호다. 조직 사전이 잘 작동한 이유는 AI 조직이 **닫힌 집합**이기 때문인데, **모델명도 동일하게 닫힌 집합**이다.

> **결정**: v0.1 §2.2의 `_MODEL_RE` 단독 방식을 폐기하고, **패밀리 사전 매칭 후 버전 토큰만 캡처**하는 방식으로 교체한다(§5).

### 2.2 HuggingFace 항목: 게이트3 예외 (신규 발견)

HF 컬렉터의 필드 형태:
```python
title   = model_id                                  # "zai-org/GLM-5.2"
summary = f"Trending HuggingFace model by {author}"
```

v0.1 §2.6에서 **매칭 입력을 `title`로 한정**했으므로 영향이 크다:
- 개체 추출은 **오히려 유리** — `zai-org`→zhipu, `GLM-5.2`→("glm","5.2"). 구조화돼 있음
- 그러나 **게이트3(제목 Jaccard)이 무의미** — model_id와 뉴스 헤드라인은 공통 토큰이 거의 없음

A0 표 4번 행이 이 사례다(MarkTechPost "Alibaba Qwen-Audio-3.0-TTS" vs HF "Qwen3.6 GGUF 파생"). 추가로 HF trending은 **공식 릴리스가 아닌 제3자 재업로드**를 자주 포함해 origin으로서의 신뢰도가 다른 소스와 다르다.

> **결정**: HF 항목은 **게이트1·2만 적용하고 게이트3(Jaccard 타이브레이커)은 건너뛴다.** 타이브레이커가 필요한 상황에서 HF 후보와 비-HF 후보가 경합하면 **비-HF origin을 우선**한다(공식 발표 우선 원칙).

### 2.3 시간창: 상수 유지 + 설정화 (A0-3 근거)

A0에서 근접 사례의 시차가 **+159h**로 관측됐으나, 이는 **매칭 실패 사례**에서 나온 값이라 양성 분포의 근거가 될 수 없다. A0 보고서가 "확정 아님"으로 표시한 판단이 옳다.

> **결정**: `+48h` 유지. 단 `scoring_policies.py`가 아닌 **`config.py` 상수로 노출**해 A2b 재개 시 코드 수정 없이 조정 가능하게 한다.

---

## 3. 목표 (Goals)

**P0 — 선행 수정 (A1 리뷰 반영)**
1. `SqliteEventRepository.upsert()`의 `is_briefed`/`briefed_at` **단조 증가** 보장.
2. 빈 `event_id` upsert **거부**(`ValueError`).

**A2a — Clusterer 순수 로직**
3. `app/domain/services/clusterer.py` — I/O 없는 순수 함수 `cluster(items) -> list[Event]`.
4. 개체 추출 v2 (조직 사전 + 모델 패밀리 화이트리스트).
5. 3게이트 + HF 예외(§2.2).
6. `event_id` 생성 강제 (origin `url_hash` 기반, 멱등).

**A3 — Phase 2 배선**
7. `ItemRepositoryPort.get_unbriefed_since(since)` + SQLite 구현.
8. `DailyBriefingUseCase` 신설.
9. `CollectTrendsUseCase`에서 브리핑 책임 제거 → `publisher` 의존 해제.
10. `BriefingGenerator` Event 단위 digest (**Discord 1회 1메시지**).
11. `POST /briefing/run` 수동 트리거.
12. APScheduler 인프로세스 등록 (수집 / 브리핑 2종).

---

## 4. 비목표 (Non-Goals)

- **A2b(양성 골든 fixture)** — 2주 관측 후 재평가(§1.3).
- **origin 컬렉터 확장** — 중국 랩 HF 흡수 결정 유지.
- **origin ↔ origin 병합** — v0.1 §2.5 그대로 이월.
- **LLM 한국어 요약** — 계속 보류.
- **Mongo 어댑터**, **`int`→`str` ID 전면 전환** — 부채 기록만.
- **corroboration/diversity 가중치 값 튜닝** — 경로만 만들고 값은 MVP 가동 후.
- **나머지 coverage 3개**(MIT TR·Verge·Decoder).
- **이미 브리핑된 38건 소급 처리** — `is_briefed=1`이므로 자연히 제외(§7.4).

---

## 5. 개체 추출 v2

```python
# app/domain/services/entity_extractor.py  (신규, 순수 함수)

_ORG_ALIASES = {
    "openai":      {"openai"},
    "anthropic":   {"anthropic", "claude"},
    "google":      {"google", "deepmind", "google deepmind", "gemini"},
    "meta":        {"meta", "meta ai", "facebook"},
    "mistral":     {"mistral", "mistral ai"},
    "nvidia":      {"nvidia"},
    "huggingface": {"huggingface", "hugging face"},
    "deepseek":    {"deepseek"},
    "alibaba":     {"alibaba", "qwen"},
    "moonshot":    {"moonshot", "kimi"},
    "zhipu":       {"zhipu", "glm", "zai-org", "zai"},
    "microsoft":   {"microsoft", "phi"},
    "xai":         {"xai", "grok"},
    "cohere":      {"cohere", "command"},
}

_MODEL_FAMILIES = {
    "gpt", "claude", "llama", "gemini", "qwen", "mistral", "mixtral",
    "codestral", "deepseek", "kimi", "glm", "cosmos", "nemotron",
    "phi", "grok", "command", "minicpm", "gemma", "falcon", "yi",
}

_VERSION_RE = re.compile(r"^(\d+(?:\.\d+)*)")   # 패밀리 직후 버전만 캡처
```

**추출 절차**
1. `title` 소문자화, 하이픈·언더스코어·슬래시를 공백으로 치환, 토큰 분리
2. **조직**: `_ORG_ALIASES` 값과 완전 일치(1~2 토큰 윈도우) → canonical 키 수집
3. **모델**: 토큰이 `_MODEL_FAMILIES`에 있으면, 같은 토큰에 붙은 숫자 또는 다음 토큰에서 `_VERSION_RE` 캡처
   - `gpt-5.5` → `("gpt","5.5")` / `qwen3.6` → `("qwen","3.6")` / `llama 4` → `("llama","4")`
   - 버전이 없으면 `("cosmos", "")` — 패밀리만으로도 유효한 개체
4. 반환: `{"org": set[str], "model": set[tuple[str,str]]}`

**이 방식이 A0 오탐 3건을 구조적으로 배제하는 이유**: `february`·`scholars`·`autoscout`는 `_MODEL_FAMILIES`에 없으므로 애초에 후보에 오르지 않는다. 날짜 가드를 별도로 붙일 필요가 없다.

> 사전 확장은 **비목표가 아니다.** 새 모델 패밀리 등장 시 상수에 한 줄 추가하는 것을 정상 유지보수로 간주한다(`COLLECTORS.md`와 동일 성격).

---

## 6. 매칭 게이트 (v0.1 §2.3 + HF 예외)

```
for coverage_item in coverage_items:
    후보 = [o for o in origin_items if 게이트1(o, coverage_item)]
    후보 = [o for o in 후보 if 게이트2(o, coverage_item, len(후보))]
    if len(후보) == 0: continue                  # 미귀속 (폐기 아님)
    if len(후보) == 1: 확정 = 후보[0]
    else:             확정 = 게이트3(후보, coverage_item)
```

| 게이트 | 규칙 | HF origin일 때 |
|---|---|---|
| **1. 시간창** | `origin.published_at - 6h ≤ coverage.published_at ≤ origin.published_at + 48h` | 동일 적용 |
| **2. 개체** | 조직 교집합 ≥1 **AND** (모델 교집합 ≥1 **OR** 게이트1 통과 후보가 유일) | 동일 적용 |
| **3. 타이브레이커** | 제목 토큰 Jaccard 최고점 → 동점 시 시각 근접 | **건너뜀.** 비-HF 후보 우선, 전부 HF면 시각 근접만 적용 |

**모델 교집합 판정**: 패밀리가 같고 버전이 양쪽 다 존재하면 버전까지 일치해야 한다. 한쪽 버전이 비어 있으면 패밀리 일치만으로 인정한다(`("cosmos","")` vs `("cosmos","3")` → 일치).

**단일 귀속**(v0.1 §2.4) 유지: coverage 1건은 최대 1개 Event에만 귀속.

---

## 7. A3 배선 상세

### 7.1 `get_unbriefed_since`

```python
# ItemRepositoryPort
async def get_unbriefed_since(self, since: datetime) -> list[CollectedItem]: ...
```
SQLite 구현: `WHERE is_briefed = 0 AND published_at >= ?`. **`id`를 `CollectedItem`에 실어 반환해야** `EventMember.item_id`와 `mark_briefed`가 동작한다 — 현재 `CollectedItem`에 id 필드가 없으므로, 반환을 `list[tuple[int, CollectedItem]]`로 하거나 매퍼에서 주입할지 **구현 시 택일하고 리뷰 노트에 근거를 남긴다.**

### 7.2 `DailyBriefingUseCase`

```python
async def execute(self) -> dict:
    since  = now_utc() - timedelta(hours=settings.LOOKBACK_HOURS)   # 48
    items  = await self._items.get_unbriefed_since(since)
    events = cluster(items)                       # 순수 함수 (A2a)
    for e in events:
        score_event(e)
        await self._events.upsert(e)              # 멱등, is_briefed 단조 (P0)
    selected = select_top_k(events, k=settings.TOP_K, floor=settings.MIN_SCORE_FLOOR)
    if selected:
        await self._publisher.publish(render_digest(selected))
        for e in selected:
            await self._events.mark_briefed(e.event_id)
            for m in e.members:
                await self._items.mark_briefed(m.item_id)
    return {"items": len(items), "events": len(events), "briefed": len(selected)}
```

### 7.3 `CollectTrendsUseCase` 정리

- 제거: `briefable` 계산 / `publisher.publish` / `mark_briefed` 블록 / `publisher` 파라미터
- 유지: `collect → exists_by_hash → apply_score → save`
- 결과: `/collect`와 `/collect/coverage`의 차이가 **컬렉터 목록뿐**이 되어 `publisher=None` 트릭 은퇴

> **기존 테스트 영향**: `test_coverage_use_case_never_briefs`가 `result["briefed"] == 0`을 단언한다. 반환 dict에서 `briefed` 키가 사라지므로 **이 테스트는 갱신 대상**이다. "publisher 인자가 더 이상 존재하지 않음"을 검증하는 형태로 바꾸고, 변경 사유를 리뷰 노트에 명시한다.

### 7.4 첫 실행 시 빈 브리핑 주의

A0에서 발행된 38건은 `is_briefed=1`이므로 `get_unbriefed_since`에서 제외된다. **첫 Phase 2 실행 결과가 비어 보일 수 있으며 이는 정상이다.** 놀라지 않도록 로그에 `items=0`을 명시적으로 남긴다.

### 7.5 브리핑 출력 (Discord 1회 1메시지)

```
[Perix Sentinel · 2026-07-22 08:00 KST]

1. OpenAI, GPT-5.5 에이전트 API 공개
   origin : OpenAI Blog
   echo   : TechCrunch, MarkTechPost (2)
   score  : 34 (critical)
   https://openai.com/...
```
- echo가 0인 Event도 점수만 높으면 브리핑된다(초기에는 대부분 이 형태일 것). `echo: —`로 표기.
- Discord 2000자 제한 초과 시 요약 길이를 줄여 1메시지 유지.

### 7.6 스케줄러 (APScheduler 인프로세스)

A0-4에서 **단일 컨테이너(uvicorn 1 프로세스)** 확인 → 외부 cron 불필요.

```python
# config.py 신규 상수
BRIEFING_TZ      = "Asia/Seoul"
BRIEFING_HOUR    = 8
TOP_K            = 5
MIN_SCORE_FLOOR  = 10
LOOKBACK_HOURS   = 48
MATCH_WINDOW_AFTER_H  = 48
MATCH_WINDOW_BEFORE_H = 6
COLLECT_INTERVAL_H    = 3
```

| 잡 | 트리거 |
|---|---|
| 수집 | `interval`, `COLLECT_INTERVAL_H` — origin + coverage 순차 |
| 브리핑 | `cron`, `hour=8`, `timezone="Asia/Seoul"` |

**저장은 UTC, 스케줄·표시만 KST.** 내부 datetime 정책(aware UTC) 불변. `main.py` lifespan에서 시작/종료(기존 `init_db` 패턴 옆).

---

## 8. 절차 (P0 ~ P5)

| 단계 | 내용 | 게이트 |
|---|---|---|
| **P0** | A1 리뷰 2건 수정 + 회귀 테스트 2개 | 그린 후 진행 |
| **P1** | `entity_extractor.py` — 개체 추출 v2 | A0 100건 샘플 재측정, **오탐 0 확인** |
| **P2** | `clusterer.py` — 3게이트 + HF 예외 | 음성 5쌍 + 경계 테스트 그린 |
| **P3** | `get_unbriefed_since` + `DailyBriefingUseCase` + `BriefingGenerator` | — |
| **P4** | `CollectTrendsUseCase` 정리 + `/briefing/run` | 기존 테스트 갱신 포함 |
| **P5** | APScheduler + config 상수 | 수동 트리거로 실가동 검증 후 등록 |

> **P2에서 한 번 끊는다.** 매칭 품질을 확인하고 게이트 파라미터를 조정한 뒤 P3로 넘어간다.

---

## 9. 테스트 계획

**P0 회귀 (2)**
| 테스트 | 내용 |
|---|---|
| `test_upsert_preserves_briefed` | `mark_briefed()` 후 동일 `event_id` upsert → `is_briefed=True`, `briefed_at` 유지 |
| `test_upsert_rejects_empty_event_id` | 빈 `event_id` upsert → `ValueError` |

**P1 개체 추출 (3)**
| 테스트 | 내용 |
|---|---|
| `test_extract_org` | `_ORG_ALIASES` 별칭 정상 매핑 (`zai-org`→zhipu 포함) |
| `test_extract_model_variants` | `GPT-5.5` / `qwen3.6` / `Llama 4` / `Cosmos`(버전 없음) |
| `test_extract_rejects_a0_false_positives` | **A0 실측 오탐 3건**이 모델로 추출되지 않음 |

**P2 클러스터링 (6)**
| 테스트 | 내용 |
|---|---|
| `test_clusterer_a0_negative_pairs` | **A0 음성 5쌍(실데이터)이 전부 미매칭** |
| `test_clusterer_time_window` | +49h·-7h 탈락 / +47h·-5h 통과 |
| `test_clusterer_entity_gate` | 조직만 겹치고 모델 다름 + 후보 2개 → 미매칭 |
| `test_clusterer_tiebreak` | 후보 2개 → Jaccard 높은 쪽 선택 |
| `test_clusterer_hf_skips_gate3` | HF origin 후보 경합 시 비-HF 우선(§2.2) |
| `test_clusterer_single_assignment` | coverage 1건이 Event 2개에 중복 귀속 안 됨 |
| `test_event_id_idempotent` | 동일 origin 재클러스터링 → 동일 `event_id` |

**P3~P5 배선 (4)**
| 테스트 | 내용 |
|---|---|
| `test_get_unbriefed_since` | `is_briefed=1` 및 창 밖 항목 제외 |
| `test_top_k_selection` | 6개 중 5개, 바닥점수 미달 제외 |
| `test_no_double_briefing` | `is_briefed=1` Event 재발행 안 됨 |
| `test_collect_no_longer_briefs` | `CollectTrendsUseCase` 실행 시 publish 호출 0 |

**전제**: 기존 66 passed 유지. `test_coverage_use_case_never_briefs`는 §7.3에 따라 **의도적 갱신**(사유를 리뷰 노트에 명시).

---

## 10. Definition of Done

**P0**
- [ ] `upsert()`가 `is_briefed`/`briefed_at`을 단조 증가로만 갱신
- [ ] 빈 `event_id` upsert 시 `ValueError`
- [ ] 회귀 테스트 2개 그린

**A2a**
- [ ] `entity_extractor.py` 순수 함수, 조직 사전 + 모델 패밀리 화이트리스트
- [ ] **A0 100건 재측정에서 모델 오탐 0** (`February 2026` 등 3건 배제 확인)
- [ ] `clusterer.py` **I/O·DB 접근 0**
- [ ] 3게이트 + HF 게이트3 예외 구현
- [ ] 매칭 입력이 `title` 한정 (boilerplate 회피)
- [ ] `event_id` 생성 강제 — 빈 값으로 Event 생성 불가
- [ ] **A0 음성 5쌍 전부 미매칭** 테스트 그린
- [ ] 경계 테스트(시간창·타이브레이커·단일귀속·멱등) 그린

**A3**
- [ ] `get_unbriefed_since()` + item id 전달 방식 확정 및 근거 기록(§7.1)
- [ ] `DailyBriefingUseCase` — cluster → score → upsert → Top-K → publish → mark_briefed
- [ ] `CollectTrendsUseCase`에서 브리핑 로직·`publisher` 인자 제거
- [ ] `/collect/coverage`의 `publisher=None` 특수 배선 소멸 확인
- [ ] `BriefingGenerator` Event 단위, **Discord 1회 1메시지**, 2000자 이내
- [ ] `POST /briefing/run` 동작
- [ ] `config.py` 상수 9개 정의(§7.6)
- [ ] APScheduler 인프로세스 등록 (수집 interval / 브리핑 cron KST 08:00), lifespan 연동
- [ ] 실가동: `/briefing/run` 1회 → Event 생성·Top-5·Discord **1메시지** 확인
- [ ] **첫 실행이 빈 결과여도 정상**임을 로그로 확인(§7.4)

**공통**
- [ ] 신규 외부 의존성 = APScheduler **1개만**
- [ ] 기존 66 + 신규 15종 그린 (갱신 테스트 사유 기록)
- [ ] `Directory_Structure.md` 현행화
- [ ] PROGRESS.md 기록: 2-Phase 전환 완료 / A2b 보류 사유 및 재개 조건(§1.3) / 미결 4건 — `int`→`str` ID, Mongo datetime 밀리초 절삭, origin 병합, **HF title 구조 문제**

---

## 부록: A0 음성 5쌍 (P2 fixture 원본)

| # | coverage | origin 후보 | 기대 결과 |
|---|---|---|---|
| 1 | TechCrunch "Anthropic's $1.5B copyright settlement" (07-21) | Anthropic "AI for Science grants" (07-20) | 미매칭 (모델 교집합 0) |
| 2 | MarkTechPost "NVIDIA srt-slurm 튜토리얼" (07-21) | NVIDIA GTC 키노트 3건 (07-21) | 미매칭 |
| 3 | MarkTechPost "NVIDIA Cosmos 3 Edge 출시" (07-21) | NVIDIA "Post-Train Cosmos 3 in One Day" (07-14) | 미매칭 (**시간창 +159h 초과**) |
| 4 | MarkTechPost "Alibaba Qwen-Audio-3.0-TTS" (07-20) | HuggingFace "Qwen3.6 GGUF 파생" (07-20) | 미매칭 (**HF 예외 경로**) |
| 5 | MarkTechPost "MiniCPM5-1B on Claude Fable 5" (07-20) | Anthropic "AI for Science grants" (07-20) | 미매칭 |

> 3번은 **모델 패밀리(`cosmos`)가 일치하므로 게이트2는 통과**한다. 게이트1(시간창)에서 탈락하는 것이 정상 경로다 — 이 케이스는 게이트 순서가 제대로 작동하는지 검증하는 역할을 겸한다.
> 4번은 게이트3 HF 예외 경로를 타는 유일한 실데이터 사례다.

---

## 부록 2: 참고 실제 코드

- `app/domain/models/event.py`, `app/domain/ports/event_repository.py` — A1 산출물
- `app/infrastructure/repositories/sqlite_event_repository.py` — P0 수정 대상
- `app/application/use_cases/collect_trends.py` — P4 정리 대상
- `app/domain/services/scoring_engine.py` / `scoring_policies.py` — corroboration 가중치 추가
- `app/domain/services/briefing_generator.py` — Event digest 전환
- `app/interface/api/collect.py` — `_run()` 구조, `publisher=None` 제거 지점
- `app/main.py` — lifespan(`init_db` 옆에 스케줄러)
- `tests/test_event_repository.py` — P0 회귀 테스트 추가 위치
