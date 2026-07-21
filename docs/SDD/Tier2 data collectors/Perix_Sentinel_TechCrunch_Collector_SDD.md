# Perix Sentinel — TechCrunch Collector SDD (첫 coverage 소스)

> Software Design Document · v0.1
> 목적: **Tier2(coverage) 라인업의 첫 소스로 TechCrunch를 추가한다.** `function=coverage`·`domain=media`. 공식 RSS 기반, 스크래핑 리스크 없음.
> 선행: origin 11개 적재 중. 후속: MIT TR·The Verge·MarkTechPost·The Decoder(각 별도), Clusterer + Event 모델(§6 의존).

---

## 0. 한 줄 요약

TechCrunch RSS를 **하나의 `CollectorPort` 구현으로 추가**한다. 수집 메커니즘은 **NVIDIA·GR RSS 컬렉터의 형제**(feedparser)라 쉽다. 하지만 이건 **첫 `coverage` 소스**라서, 앞선 origin 컬렉터에 없던 **결정적 이슈**가 있다 — **Clusterer가 아직 없는 상태에서 coverage 항목이 파이프라인에 들어가면 origin 사건처럼 브리핑돼 버린다.** 이 SDD의 핵심은 그걸 **`publisher=None` 배선으로 막는 것**(store-only). **스코어링 파일은 무수정.**

---

## 1. 맥락: 왜 이건 origin 컬렉터와 다른가

```
origin (원천)     OpenAI·NVIDIA·... → 사건 생성 → 스코어 → 브리핑 ✅
coverage (비교군)  TechCrunch ←여기 → 사건을 "커버" → (Clusterer로 origin에 매칭) → 중요도 가산
```

origin은 곧바로 브리핑되어도 맞다("무슨 일이 일어났나"). 하지만 coverage는 **그 자체가 브리핑 대상이 아니다.** TechCrunch의 "OpenAI가 GPT 에이전트 발표" 기사는 **새 사건이 아니라 OpenAI 발표의 메아리**다. 이 메아리를 브리핑하면 같은 사건이 두 번 나간다 → "signal over noise"에 정면 위배.

---

## 2. 이 SDD의 핵심 문제 (Clusterer 부재 시 처리)

### 2.1 실제 파이프라인 동작 (확인됨)

`CollectTrendsUseCase.execute()`는 모든 항목에:
1. `apply_score(item)` 실행
2. DB 저장
3. `item.score >= BRIEFING_THRESHOLD(15)` 이면 **브리핑 발행**

### 2.2 위험

TechCrunch는 `SOURCE_WEIGHTS`에 없어 source 점수 0, popularity 0. **그러나 `keyword_score`는 걸린다.**
- 예: "OpenAI's new **GPT** **agent** with **reasoning**" → `gpt`(4)+`agent`(5)+`reasoning`(5)=14, + recency → **15 초과 → 브리핑됨.**
- → coverage 기사가 **origin 사건인 척 Discord에 나간다.** 원칙 위배.

### 2.3 결정: `publisher=None` store-only 배선

`CollectTrendsUseCase`는 이미 `publisher: PublisherPort | None = None`을 받고, `if briefable and self._publisher is not None:`로 가드한다.
→ **coverage 컬렉터는 `publisher=None`으로 실행**하면 **저장은 하되 절대 브리핑하지 않는다.** 이 배선은 **별도 엔드포인트 `POST /collect/coverage`로 분리**해 불변식을 API 경계에 명시한다(§8 A3). origin `/collect`와 공통 러너를 공유해 중복은 없다.

- 장점: **스코어링 파일 무수정**(비목표 준수). 배선(interface 레이어)만 손댐.
- 효과: coverage 항목은 DB에 쌓여 **미래 Clusterer 매칭 재료**가 되지만, Clusterer 완성 전까지 브리핑 오염 0.
- `apply_score`는 그대로 돌게 둔다(무해 — 점수는 저장만 되고 브리핑엔 안 쓰임). Clusterer+스코어 재설계 때 재해석.

---

## 3. 목표 (Goals)

1. `TechCrunchRssCollector`가 `CollectorPort`를 구현하고, 단독 실행 시 **≥1건 반환**한다.
2. `source="TechCrunch"` 고정.
3. `metadata`에 **`function=coverage`·`domain=media`·`region=us`·`feed=...`** 부착.
4. `collect.py`에서 **coverage 전용 엔드포인트(`/collect/coverage`, `publisher=None`)**로 등록 → store-only.
5. 공통 인프라(`feedparser`·`parse_struct_time`·`now_utc`) 재사용, 신규 유틸 0.
6. 골든 fixture 테스트 1개.

---

## 4. 비목표 (Non-Goals)

- **Clusterer / Event 모델 / 매칭** — 이 SDD 밖. coverage 항목은 지금은 그냥 저장만.
- **스코어링 파일 수정** — `SOURCE_WEIGHTS`·`scoring_engine`·`scoring_policies` 무수정. (coverage를 popularity/corroboration에 반영하는 건 Tier2 재보정 단계)
- **coverage 항목 브리핑** — §2.3으로 원천 차단. 지금 브리핑 로직에 coverage 개념을 넣지 않는다.
- **나머지 coverage 소스 4개** — 각각 별도 SDD(같은 패턴).
- **origin 컬렉터 배선 변경** — 기존 origin은 그대로 `publisher` 받아 브리핑.

---

## 5. 피드 선택 & 관련성

TechCrunch는 fintech·가젯 등 비-AI가 많다. coverage 목적상 **AI 카테고리 피드**를 우선.

| 후보 | URL | 비고 | 채택 |
|---|---|---|---|
| **AI 카테고리** | `techcrunch.com/category/artificial-intelligence/feed/` | 사전 필터됨 | ✅ 1순위 (A0 확인) |
| 전체 피드 | `techcrunch.com/feed/` | 전문 RSS·페이월 없음, 단 비-AI 다량 | 폴백(+키워드 필터 필요) |

- A0에서 AI 카테고리 피드가 정상 파싱되면 그대로. → **필터 불필요**.
- 폴백(전체 피드) 사용 시 → HN식 `\b` 키워드 필터 이식.

---

## 6. RSS 계약 (A0에서 확정)

> ⚠️ 설계 가정. A0에서 실제 피드 덤프 후 필드 고정(NVIDIA·GR과 동일 원칙).

- **엔드포인트**: `techcrunch.com/category/artificial-intelligence/feed/` (§5)
- **형식**: RSS 2.0 → `feedparser`. `feed.bozo` 경고 로깅.

### 필드 매핑

| CollectedItem | entry 출처 | 비고 |
|---|---|---|
| `source` | 고정 `"TechCrunch"` | |
| `title` | `entry.get("title","")` | `.strip()` |
| `url` | `entry.get("link","")` | `.strip()`. `url_hash` 입력 |
| `published_at` | `entry.published_parsed` | `parse_struct_time(...)` if 존재 else `now_utc()` |
| `summary` | `entry.get("summary","")` | `.strip()`. TechCrunch는 발췌 제공 |
| `tags` | `["techcrunch"]` (+ A0 category) | |
| `metadata` | 아래 §7 | |

### A0 확인 3가지
1. AI 카테고리 피드 URL 정상 파싱 여부(§5 1순위).
2. `published_parsed` 채워지는지(RFC822 → `parse_date` 폴백 경로).
3. `summary`가 발췌인지 전문인지(매칭 시 텍스트 품질에 영향).

---

## 7. 태그 (metadata)

```python
metadata = {
    "function": "coverage",   # ← 첫 coverage 소스
    "domain":   "media",      # ← 신규 domain 값 (COLLECTORS.md §0에 추가 필요)
    "region":   "us",
    "feed":     "techcrunch-ai",
}
```

> ⚠️ `domain=media`는 **COLLECTORS.md §0 domain 목록에 없던 신규 값**이다. 이 SDD가 첫 도입 → 문서 §0에 `media` 추가 필요(태깅 정책의 "나머지 절반"이 여기서 정의됨).
> `function=coverage`는 지금은 아무도 소비하지 않지만, Clusterer가 오면 **`function=coverage`로 쿼리해 매칭 대상을 고른다** → 지금 박아두는 게 포워드-호환.

---

## 8. 절차 (A0 ~ A4)

| 단계 | 내용 |
|---|---|
| **A0 관측** | AI 카테고리 피드 확정 + §6 3가지 확인. `docs/notes` 기록 |
| **A1 파서** | `TechCrunchRssCollector` 작성. `NvidiaRssCollector` 복사 후 URL·source·metadata 교체 |
| **A2 정규화** | 제목·요약 `.strip()`, 날짜 fallback, coverage 태그 부착 |
| **A3 배선** | **coverage 전용 엔드포인트 `POST /collect/coverage`** 신설(§2.3). 내부는 `publisher=None`. origin `/collect`와 공통 러너 공유 |
| **A4 테스트** | 골든 fixture 1개 + `/collect/coverage` 실가동 시 **DB 적재되나 브리핑 0** 확인 |

### A3 배선 예시 (공통 러너 + 엔드포인트 2개)

```python
# 공통 러너 — 중복 제거의 핵심
async def _run(collectors: dict, repository, publisher) -> dict:
    results = {}
    for name, c in collectors.items():
        results[name] = await CollectTrendsUseCase(c, repository, publisher).execute()
    return results

@router.post("/collect")            # origin: publisher 받아 브리핑
async def trigger_collect() -> dict:
    return await _run(ORIGIN_COLLECTORS, SqliteItemRepository(), DiscordPublisher())

@router.post("/collect/coverage")   # coverage: publisher=None → store-only
async def trigger_collect_coverage() -> dict:
    return await _run(COVERAGE_COLLECTORS, SqliteItemRepository(), publisher=None)
```

> 두 엔드포인트가 셋업·루프를 복붙하지 않고 `_run`을 공유 → 관심사 분리가 중복 없이 성립.
> 미래: Clusterer 도입 시 `/collect/coverage`에 **매칭 스텝**을 붙이는 자리가 이미 마련됨(2단계 파이프라인 선반영).

---

## 9. 테스트 계획

`test_arxiv_collector_golden.py` 패턴 준수:
- **fixture**: `tests/fixtures/techcrunch_feed.xml` + `techcrunch_feed.golden.json` (3건 트림)
- **모킹**: `monkeypatch.setattr(feedparser, "parse", ...)` — 네트워크 없이
- **비교 필드**: `source/title/url/summary/tags/metadata`(특히 `metadata["function"]=="coverage"`)·`published_at`
- **배선 테스트(권장)**: coverage use case를 `publisher=None`으로 실행 시 **브리핑 0건** 단위 검증

---

## 10. Definition of Done

- [ ] `TechCrunchRssCollector`가 `CollectorPort` 구현, 단독 실행 시 ≥1건 반환
- [ ] `source="TechCrunch"` 고정
- [ ] A0에서 AI 카테고리 피드 확정, 필드·fallback 기록
- [ ] `published_at`이 `parse_struct_time` + `now_utc()` fallback
- [ ] `metadata`에 `function=coverage`·`domain=media`·`region=us`·`feed` 부착
- [ ] **`/collect/coverage` 엔드포인트 신설(`publisher=None`)** + origin과 공통 러너 공유(중복 없음)
- [ ] `/collect/coverage` 실가동: TechCrunch 항목 **DB 적재 O, 브리핑 0** 확인
- [ ] 골든 fixture 테스트 1개 + (권장)브리핑 0 배선 테스트, 전체 그린
- [ ] **스코어링 파일 무수정**
- [ ] **COLLECTORS.md §0 domain 목록에 `media` 추가** (문서 동기화)
- [ ] PROGRESS에 "coverage store-only 배선 도입 / Clusterer 전까지 브리핑 차단" 기록
- [ ] 신규 유틸 0 확인

---

## 부록: 참고 실제 코드

- `app/infrastructure/collectors/nvidia_rss_collector.py` / `openai_rss_collector.py` — 복사 기반
- `app/application/use_cases/collect_trends.py` — `publisher=None` 가드 확인(§2.3 근거)
- `app/domain/services/scoring_engine.py` — `_keyword_score`가 coverage도 점수 줌(§2.2 위험 근거)
- `app/interface/api/collect.py` — 배선 지점(origin/coverage 분리)
- `tests/test_arxiv_collector_golden.py` — 골든 패턴
