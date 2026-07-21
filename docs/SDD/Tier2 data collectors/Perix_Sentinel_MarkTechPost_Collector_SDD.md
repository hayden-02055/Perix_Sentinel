# Perix Sentinel — MarkTechPost Collector SDD (두 번째 coverage 소스)

> Software Design Document · v0.1
> 목적: **Tier2(coverage) 라인업의 두 번째 소스로 MarkTechPost를 추가한다.** `function=coverage`·`domain=media`. 공식 RSS 기반.
> 선행: TechCrunch(첫 coverage 소스) 완료 — store-only 배선(`publisher=None`, `/collect/coverage`)이 이미 구축됨. 이 SDD는 그 배선을 **재사용**만 한다.
> 후속: TechCrunch + MarkTechPost 2개 소스 확보 후 **Clusterer + Event 모델 SDD** 착수(이 SDD의 목적).

---

## 0. 한 줄 요약

MarkTechPost RSS를 **두 번째 `coverage` `CollectorPort` 구현으로 추가**한다. TechCrunch SDD에서 이미 해결한 "coverage가 Clusterer 없이 브리핑되면 안 된다"는 문제는 **기존 `/collect/coverage`(`publisher=None`) 엔드포인트에 편입**하는 것으로 끝난다 — 새로 설계할 것이 없다. 이 SDD의 실질적 관심사는 **MarkTechPost 고유의 콘텐츠 성격(모델 릴리스 요약)이 TechCrunch(속보)와 다르다는 점**과, 그로 인한 필드·필터링 차이뿐이다. **스코어링 파일은 여전히 무수정.**

---

## 1. 맥락: TechCrunch와 뭐가 다른가

```
TechCrunch    → 속보·비즈니스 (펀딩·런칭 타이밍)      → echo 강점: 빠른 반응 속도
MarkTechPost  → AI 전문 매체 (모델 릴리스/논문 요약)   → echo 강점: origin 발표와 내용 밀도 가장 근접
```

Origin 소스 9개 중 다수(OpenAI·Anthropic·Mistral·Meta·DeepMind·NVIDIA·Google Research)가 **모델/연구 릴리스 발표**다. MarkTechPost는 "새 모델이 나오면 요약 기사를 쓰는" 매체라, **Clusterer가 매칭할 첫 실전 사례로 origin↔coverage 콘텐츠 유사도가 가장 높다.** TechCrunch 하나로는 "속보 echo"만 검증되므로, 이 소스가 추가돼야 **"내용 밀착형 echo"**까지 커버된다 — 지난 논의에서 이 SDD를 최우선으로 잡은 이유.

**설계 차이점(예상)**:
- TechCrunch는 비-AI 기사가 섞여 AI 카테고리 피드가 필요했다. **MarkTechPost는 매체 전체가 AI/ML 전문**이라 카테고리 필터 불필요 — 전체 피드(`marktechpost.com/feed/`) 그대로 사용 가능(§5).
- TechCrunch `summary`는 발췌 수준이었다. MarkTechPost는 "byte-size 요약" 스타일이라 요약문 자체가 이미 압축된 정보 — Clusterer 매칭 텍스트 품질에 유리할 수 있음(A0에서 확인).

---

## 2. Store-only 배선 재확인 (재설계 아님)

TechCrunch SDD에서 이미 구현·검증된 것:

```python
@router.post("/collect/coverage")
async def trigger_collect_coverage() -> dict:
    collectors = {
        "techcrunch": TechCrunchRssCollector(),
    }
    return await _run(collectors, SqliteItemRepository(), publisher=None)
```

이 SDD가 하는 일은 이 dict에 **한 줄 추가**하는 것뿐이다:

```python
collectors = {
    "techcrunch": TechCrunchRssCollector(),
    "marktechpost": MarkTechPostRssCollector(),   # ← 추가
}
```

`publisher=None` 가드, `_run()` 공통 러너, 브리핑 차단 로직 — 전부 그대로 재사용. **새로운 아키텍처 결정 없음.**

---

## 3. 목표 (Goals)

1. `MarkTechPostRssCollector`가 `CollectorPort`를 구현하고, 단독 실행 시 **≥1건 반환**한다.
2. `source="MarkTechPost"` 고정.
3. `metadata`에 **`function=coverage`·`domain=media`·`region=us`·`feed=...`** 부착 (TechCrunch와 동일한 axis 값 재사용 — `media`는 이미 COLLECTORS.md §0에 등록돼 있어 신규 도입 없음).
4. `collect.py`의 `/collect/coverage` 딕셔너리에 **한 줄 등록**.
5. 공통 인프라(`feedparser`·`parse_struct_time`·`now_utc`) 재사용, 신규 유틸 0.
6. 골든 fixture 테스트 1개 + (TechCrunch 패턴과 동일한) 브리핑 0건 배선 테스트.

---

## 4. 비목표 (Non-Goals)

- **Clusterer / Event 모델 / 매칭** — 이 SDD 밖. TechCrunch와 마찬가지로 지금은 저장만.
- **스코어링 파일 수정** — `SOURCE_WEIGHTS`·`scoring_engine`·`scoring_policies` 무수정.
- **store-only 배선 재설계** — §2에서 이미 확정. 이 SDD는 소비만 한다.
- **나머지 coverage 소스(MIT TR·Verge·Decoder)** — 각각 별도 SDD.
- **카테고리별 서브피드 세분화** — MarkTechPost는 매체 전체가 AI 전문이라 불필요(§5). 향후 필요해지면 별건.

---

## 5. 피드 선택 & 관련성

| 후보 | URL | 비고 | 채택 |
|---|---|---|---|
| **전체 피드** | `https://www.marktechpost.com/feed/` | 매체 전체가 AI/ML 전문 매체 — TechCrunch와 달리 비-AI 콘텐츠 혼입 리스크 낮음 | ✅ 1순위 (A0에서 비-AI 비율 확인) |
| 카테고리 서브피드 (예: `/category/technology/ai-tools/feed/`) | — | 매체 성격상 불필요할 가능성 높음 | A0에서 전체 피드 비-AI 비율이 임계치(Google Research 사례처럼 >15%) 넘을 때만 검토 |

> ⚠️ TechCrunch·GitHub 등과 달리, "매체 전체가 AI 전문"이라는 전제는 **외부 조사 기반 가정**이지 직접 라이브 확인은 아니다. **A0에서 반드시 실측 검증**할 것 (§8).

---

## 6. RSS 계약 (A0에서 확정 — 미확인 상태로 시작)

> ⚠️ **이 섹션은 전량 가정이다.** 이번 세션에서 marktechpost.com이 네트워크 허용 도메인 목록에 없어 실제 피드 덤프를 확인하지 못했다. TechCrunch·NVIDIA·Google Research SDD 때와 달리, **A0을 건너뛰고 넘어온 게 아니라 이 SDD 작성 시점에 아예 못 했다** — 구현 착수 전 A0이 이번엔 특히 더 필수다.

### 예상 필드 매핑 (WordPress 기반 표준 RSS 2.0 가정)

| CollectedItem | entry 출처(가정) | 비고 |
|---|---|---|
| `source` | 고정 `"MarkTechPost"` | |
| `title` | `entry.get("title","")` | `.strip()` |
| `url` | `entry.get("link","")` | `.strip()`. `url_hash` 입력 |
| `published_at` | `entry.published_parsed` | `parse_struct_time(...)` if 존재 else `now_utc()` (TechCrunch·NVIDIA와 동일 패턴) |
| `summary` | `entry.get("summary","")` | `.strip()`. **A0에서 실제로 요약인지 본문 일부인지 확인 — WordPress 피드는 종종 `<img>` 태그가 섞여 들어옴(Google Research 사례처럼)** |
| `tags` | `["marktechpost"]` (+ A0에서 확인되는 카테고리) | |
| `metadata` | 아래 §7 | |

### A0 확인 항목 (필수, 4가지 — TechCrunch보다 1개 많음)
1. `https://www.marktechpost.com/feed/`가 RSS 2.0으로 정상 파싱되는지, `feed.bozo` 여부.
2. 비-AI 콘텐츠 비율 — "매체 전체가 AI 전문"이라는 가정 실측 검증(§5). 임계치 넘으면 카테고리 서브피드로 전환.
3. `published_parsed` 채워지는지(포맷·타임존 확인).
4. `summary` 필드에 HTML 혼입(특히 `<img>` 태그) 여부 — Google Research 컬렉터 때 실제로 발견됐던 패턴이라 재발 가능성 있음.

---

## 7. 태그 (metadata)

```python
metadata = {
    "function": "coverage",
    "domain":   "media",      # TechCrunch가 이미 도입한 값 — 신규 아님
    "region":   "us",         # MarkTechPost는 California 기반 — A0에서 확인 불필요(공개 정보로 충분)
    "feed":     "marktechpost-ai",
}
```

> `function=coverage`로 이미 TechCrunch가 있으니, Clusterer 쿼리 대상이 1개→2개로 늘어난다. 이 시점부터 "coverage가 여러 개일 때 어떻게 origin 하나에 여러 echo를 매칭할지"가 Clusterer 설계에서 실제로 고려해야 할 문제가 됨(다음 SDD의 입력).

---

## 8. 절차 (A0 ~ A4)

| 단계 | 내용 |
|---|---|
| **A0 관측** | `https://www.marktechpost.com/feed/` 실제 덤프. §6 4가지 확인. `docs/notes`에 기록 (이번 세션에서 못한 부분 — **구현 착수 시 최우선**) |
| **A1 파서** | `MarkTechPostRssCollector` 작성. `TechCrunchRssCollector` 복사 후 URL·source·metadata 교체 |
| **A2 정규화** | 제목·요약 `.strip()`, 날짜 fallback, A0에서 HTML 혼입 확인되면 정제 로직 추가(비범위 초과 시 요약 원문 그대로 두고 부채 기록) |
| **A3 배선** | `/collect/coverage` 딕셔너리에 `"marktechpost": MarkTechPostRssCollector()` 한 줄 추가. 신규 엔드포인트·신규 러너 불필요(§2) |
| **A4 테스트** | 골든 fixture 1개 + `/collect/coverage` 실가동 시 **TechCrunch·MarkTechPost 둘 다 DB 적재, 브리핑 0** 확인 |

---

## 9. 테스트 계획

`test_techcrunch_collector_golden.py` 패턴 그대로 재사용:
- **fixture**: `tests/fixtures/marktechpost_feed.xml`(A0 실제 덤프에서 3건 트림) + `marktechpost_feed.golden.json`
- **모킹**: `monkeypatch.setattr(feedparser, "parse", ...)` — 네트워크 없이
- **비교 필드**: `source/title/url/summary/tags/metadata`(특히 `metadata["function"]=="coverage"`)·`published_at`
- **배선 테스트**: coverage use case를 `publisher=None`으로 실행 시 **브리핑 0건** 단위 검증 (TechCrunch 테스트와 동일 구조, 소스만 교체)
- **회귀**: 전체 스위트 그린 확인 (현재 60 passed 유지 + MarkTechPost 테스트 추가분)

---

## 10. Definition of Done

- [ ] **A0 실측 완료** — §6·§5 가정 검증(특히 비-AI 비율, HTML 혼입 여부). 이 SDD의 가정과 실측이 다르면 §6·§7 갱신 후 진행
- [ ] `MarkTechPostRssCollector`가 `CollectorPort` 구현, 단독 실행 시 ≥1건 반환
- [ ] `source="MarkTechPost"` 고정
- [ ] `published_at`이 `parse_struct_time` + `now_utc()` fallback
- [ ] `metadata`에 `function=coverage`·`domain=media`·`region=us`·`feed` 부착
- [ ] `/collect/coverage` 딕셔너리에 등록 (신규 엔드포인트 없음, 기존 재사용 확인)
- [ ] `/collect/coverage` 실가동: TechCrunch + MarkTechPost **둘 다 DB 적재, 브리핑 0** 확인
- [ ] 골든 fixture 테스트 1개 + 브리핑 0 배선 테스트, 전체 그린
- [ ] **스코어링 파일 무수정**
- [ ] PROGRESS.md에 "coverage 2번째 소스 추가 / Clusterer 입력 데이터 다양성 확보" 기록
- [ ] 신규 유틸·신규 엔드포인트 0 확인 (재사용만 했는지 검증)

---

## 부록: 참고 실제 코드

- `app/infrastructure/collectors/techcrunch_rss_collector.py` — 복사 기반(가장 가까운 형제)
- `app/interface/api/collect.py` — `/collect/coverage` dict에 한 줄 추가할 지점
- `tests/test_techcrunch_collector_golden.py` — 골든 + 배선 테스트 패턴
- `app/infrastructure/collectors/google_research_rss_collector.py` — `summary` HTML 혼입 대응 사례(§6-4 참고)
