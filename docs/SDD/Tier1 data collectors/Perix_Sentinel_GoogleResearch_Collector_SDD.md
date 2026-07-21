# Perix Sentinel — Google Research Collector SDD

> Software Design Document · v0.1
> 목적: **origin(구 Tier1) 라인업에 Google Research를 추가한다.** `core-lab` 도메인 보강. 공식 RSS 기반, 스크래핑 리스크 없음.
> 선행: origin 10/10 소스 적재 중(NVIDIA 포함, A4 완료). 후속: HF `region=cn` 태깅 / Tier2 전환.

---

## 0. 한 줄 요약

Google Research 블로그 RSS를 **하나의 `CollectorPort` 구현으로 추가**한다.
구현체는 **`NvidiaRssCollector`·`OpenAIRssCollector`의 형제**(feedparser + `parse_struct_time` + `now_utc` fallback)라 신규 인프라가 없다. 다만 이 소스는 앞선 RSS 컬렉터들과 달리 **세 가지 고유 이슈**가 있다 — ① 기존 `DeepmindHtmlCollector`와의 소스 경계 ② 피드 URL 이력이 여러 개(canonical 확정 필요) ③ 주제 폭이 LLM 밖으로 넓음(필터 필요성↑). 이 셋을 A0에서 먼저 못 박는다. **스코어링은 비범위**(기존 원칙 유지).

---

## 1. 맥락: 이 작업이 큰 그림에서 어디인가

```
origin (원천)     Google Research ←여기, DeepMind, OpenAI, NVIDIA, arXiv, ...   "무슨 일이 일어났나"
coverage (비교군)  뉴스레터, 미디어                                             "그게 얼마나 회자되나"
        ↓ 둘 다
   공통 포맷 변환 (CollectedItem)  ←이 SDD의 작업 지점
        ↓
   스코어링 = origin 신호를 coverage corroboration으로 검증  ← 나중 (비범위)
```

Google Research는 **AI/ML 기초 연구의 1차 발생원**이다. 기존 origin 라인업의 `core-lab`은 제품 중심 랩(OpenAI·Anthropic·DeepMind)에 쏠려 있는데, Google Research는 **논문·기법·시스템 레벨의 연구 발표**를 담당해 결이 조금 다르다. arXiv(academia)와 core-lab 사이를 메우는 소스다.

---

## 2. 목표 (Goals)

1. `GoogleResearchRssCollector`가 `CollectorPort` 계약을 구현하고, 단독 실행 시 **≥1건의 `CollectedItem`을 반환**한다.
2. `source="Google Research"`로 고정한다(§6 명명 규약 — DeepMind과 명확히 구분).
3. RSS 응답을 **공통 포맷으로 손실 없이 정규화**한다(제목·URL·발행일·요약).
4. 기존 컬렉터와 **동일한 공통 인프라만** 사용한다: `feedparser`, `parse_struct_time`, `now_utc`, `get_logger`. **신규 유틸 0**이 목표.
5. `metadata`에 **도메인 태그**(`domain=core-lab`, `region=us`, `function=origin`, `feed=research-blog`)를 부착한다.
6. P0 규칙대로 **골든 fixture 테스트 1개**를 추가한다.

---

## 3. 비목표 (Non-Goals)

- **스코어링 일체** — `SOURCE_WEIGHTS`에 `"Google Research"` 키 추가, popularity 축 설계, 임계값 재보정 모두 **하지 않는다**.
  - ⚠️ 결과적으로 `SOURCE_WEIGHTS.get("Google Research", 0)` → **source 점수 0**. NVIDIA·HN과 동일한 **의도된 비범위**(버그 아님). PROGRESS에 1줄 기록.
- **DeepMind과의 의미 중복 제거** — Google Research와 DeepMind이 같은 사건(예: Gemini 관련 발표)을 각자 올려도, 이 컬렉터는 **중복을 지우지 않는다.** URL이 다르므로 `url_hash` 기반 dedup에도 안 걸린다. 의미 중복 병합은 **Clusterer의 미래 책임**(이 SDD 밖). §4.1 참조.
- **다중 피드 병합** — canonical 피드 1개만. 대체 URL은 §4.2에 폴백 후보로만 기록.
- **HTML 폴백** — RSS 실패 시 그냥 실패로 둔다.
- **태그 필드 스키마 리팩터링** — 태그는 `metadata` dict에 넣는다(별건).
- **관련성 필터의 사전 확정** — §7, A0 실측 후 결정.
- LLM 요약 — RSS `summary` 그대로.

---

## 4. 소스 고유 이슈 (이 SDD의 핵심)

### 4.1 DeepMind 컬렉터와의 경계

- 이미 `DeepmindHtmlCollector`(`deepmind.google`)가 origin에 있다. Google Research(`research.google`)는 **별개 조직·별개 블로그**다.
- **판단: 별도 소스로 유지한다.** 합치지 않는다.
  - 근거: 두 블로그는 발행 주체·주제가 다르다(DeepMind=제품·프론티어 모델 / Google Research=기초 연구·시스템·기법).
  - 중복 리스크: 드물게 같은 사건을 둘 다 다룰 수 있으나, 그건 **corroboration 신호로 흡수될 대상**이지 수집 단계에서 지울 대상이 아니다("메아리를 시그널로").
- **DoD 영향**: source 문자열을 `"Google Research"`로 두어 DeepMind(`"DeepMind"`)과 확실히 분리. 스코어링·클러스터링에서 둘을 구분 가능하게.

### 4.2 피드 URL — canonical 확정 필요

Google은 AI 블로그 피드 URL을 여러 번 옮겼다. A0에서 **실제 응답으로 canonical을 확정**한다.

| 후보 URL | 상태 | 채택 |
|---|---|---|
| **`research.google/blog/rss`** | 라이브 확인(RSS 2.0 서빙) | ✅ **1순위** |
| `research.googleblog.com` (feedburner) | 구 URL, 리다이렉트 가능성 | 폴백 |
| `ai.googleblog.com/feeds/posts/default` | 구 Google AI 블로그, 통합됨 | 폴백 |
| `blog.google/technology/ai/rss` | 제품·마케팅 성격 혼입 | 미채택(노이즈) |

> A0에서 1순위가 정상 파싱되면 그대로 고정. 실패 시 폴백 순서로 재시도하고 결과를 `docs/notes`에 기록.

### 4.3 주제 폭 — 필터 필요성이 NVIDIA보다 큼

Google Research는 ML뿐 아니라 **양자컴퓨팅·분산시스템·HCI·헬스·알고리즘**까지 발표한다. AI-신호 시스템 관점에서 일부는 off-topic이다.
→ NVIDIA(대부분 GPU/AI)나 OpenAI(순수 AI)와 달리 **필터가 실제로 필요할 가능성이 높다.** §7에서 A0 실측으로 판단하되, **기본 가정을 "필터 있음" 쪽으로** 둔다(NVIDIA와 반대).

---

## 5. RSS 계약 (Ground Truth로 확정할 것)

> ⚠️ 설계 가정. A0에서 실제 피드 1건을 덤프해 필드·날짜 포맷을 확정한 뒤 파서를 고정한다.

- **엔드포인트**: `https://research.google/blog/rss` (§4.2에서 확정)
- **응답 형식**: RSS 2.0 → `feedparser`.
- **호출**: `feed = await asyncio.to_thread(feedparser.parse, RSS_URL)`, `feed.bozo` 경고 로깅(OpenAI 패턴).

### 필드 매핑 (entry → CollectedItem)

| CollectedItem | entry 출처 | 비고 |
|---|---|---|
| `source` | 고정 `"Google Research"` | §6 |
| `title` | `entry.get("title", "")` | `.strip()`. 개행/공백 정규화 여부 A0 확인 |
| `url` | `entry.get("link", "")` | `.strip()`. `url_hash` 입력 |
| `published_at` | `entry.published_parsed` | **`parse_struct_time(...)` if 존재 else `now_utc()`** |
| `summary` | `entry.get("summary", "")` | `.strip()`. 원문 그대로 |
| `tags` | 고정 `["google-research"]` (+ A0 category 발견 시 추가) | |
| `metadata` | 도메인 태그 dict | §6.2 |

### A0에서 반드시 확인할 4가지

1. **canonical 피드** — §4.2 1순위가 정상 파싱되는지.
2. **날짜 포맷** — `published_parsed`(struct_time) 채워지는지. 안 되면 `entry.published`(RFC822) → `parse_date` 폴백.
3. **카테고리/태그 존재** — `entry.tags` 유무. 있으면 §7 필터의 근거.
4. **주제 분포** — 최근 N건 중 비-AI(양자·시스템·HCI 등) 비율. → §7 필터 결정의 핵심 데이터.

---

## 6. 명명 규약 & 태그

### 6.1 source 문자열

- `source = "Google Research"`.
- ⚠️ 기존 `"DeepMind"`과 **절대 합치지 않는다**(§4.1). `SOURCE_WEIGHTS` 추가 시 키를 `"Google Research"`로 정확히 일치.

### 6.2 도메인 태그 (metadata)

```python
metadata = {
    "function": "origin",
    "domain":   "core-lab",
    "region":   "us",
    "feed":     "research-blog",
}
```

> COLLECTORS.md의 태그 체계와 1:1 대응. NVIDIA는 `domain=hardware`였고, 이건 `domain=core-lab`.

---

## 7. 관련성 필터 — A0 결과로 분기 (기본 가정: 필터 있음)

| A0 관측 결과 | 결정 |
|---|---|
| 비-AI 비율 **낮음(<15%)** | 필터 없음, 전량 통과 |
| 비-AI 비율 **높음** (예상) | **필터 적용** — `entry.tags` 카테고리 기반 제외 우선, 없으면 HN식 `\b` 키워드 매칭 |

> NVIDIA는 "무필터 기본"이었지만 Google Research는 주제가 넓어 **"필터 있음"을 기본 가정**으로 둔다. 단 최종 결정은 A0 실측이 내린다.
> 필터 방식 우선순위: **category(`entry.tags`) 기반** > 제목 키워드. category가 신뢰도 높음.

---

## 8. 절차 (A0 ~ A4)

| 단계 | 내용 |
|---|---|
| **A0 관측** | canonical 피드 확정(§4.2) → §5의 4가지 확인 → 필드·fallback·필터 확정. `docs/notes`에 기록 |
| **A1 파서** | `GoogleResearchRssCollector` 작성. `NvidiaRssCollector` 복사 후 URL·source·metadata·필터만 교체 |
| **A2 정규화** | 제목 `.strip()`(필요 시 `_normalize`), 날짜 `parse_struct_time` fallback, metadata 태그, (필요 시)필터 적용 |
| **A3 등록** | `app/interface/api/collect.py`에 `"google_research": GoogleResearchRssCollector()` 한 줄 + import 추가 |
| **A4 테스트** | 골든 fixture 1개 + `/collect` 실가동 확인 |

---

## 9. 테스트 계획 (기존 골든 패턴 준수)

`test_arxiv_collector_golden.py`·NVIDIA 테스트 구조를 그대로 따른다:

- **fixture**: `tests/fixtures/google_research_feed.xml`(실제 RSS 스냅샷) + `google_research_feed.golden.json`
- **모킹**: `monkeypatch.setattr(feedparser, "parse", lambda _url: parsed_feed)` — 네트워크 없이 실행
- **비교 필드**: `source / title / url / summary / tags / metadata / published_at`
- **필터 케이스**: 필터를 적용하기로 했다면 **비-AI 항목 1건을 fixture에 포함**해 필터아웃 검증(HN 골든의 비-AI 필터 케이스와 동일 구조)
- **published_at**: `.replace(tzinfo=None).isoformat()` 비교
- **fixture 크기**: 3~4건 트림(fixture size 부채 원칙)

---

## 10. Definition of Done

- [ ] `GoogleResearchRssCollector`가 `CollectorPort` 구현, 단독 실행 시 ≥1건 반환
- [ ] `source="Google Research"` 고정, DeepMind과 분리 확인
- [ ] A0에서 canonical 피드 URL 확정, `docs/notes`에 기록
- [ ] A0 덤프로 날짜 포맷·태그 존재·주제 분포 확정
- [ ] `published_at`이 `parse_struct_time` + `now_utc()` fallback
- [ ] `tags=["google-research"]`(+ A0 category), `metadata`에 `function/domain/region/feed` 4개 부착
- [ ] 관련성 필터 여부를 A0 근거와 함께 결정·주석화 (기본 가정: 필터 있음, category 우선)
- [ ] 골든 fixture 테스트 1개 추가(필터 시 비-AI 케이스 포함), 전체 테스트 그린
- [ ] `collect.py` 레지스트리 등록 + import, `/collect` 실가동 DB 적재 확인
- [ ] **스코어링 파일 무수정** (`SOURCE_WEIGHTS`·`scoring_engine`·`scoring_policies`)
- [ ] PROGRESS에 "Google Research source 점수 0 — 의도된 비범위" + "DeepMind 의미중복은 Clusterer로 이월" 기록
- [ ] 신규 유틸 추가 0 확인

---

## 부록: 참고한 실제 코드

- `app/infrastructure/collectors/openai_rss_collector.py` / `nvidia_rss_collector.py` — 복사 기반(형제)
- `app/infrastructure/collectors/deepmind_html_collector.py` — 소스 경계 구분 대상(§4.1)
- `app/infrastructure/collectors/hackernews_api_collector.py` — 관련성 필터(`AI_KEYWORDS`, `\b` 매칭) 패턴 이식 참고
- `app/core/datetime_utils.py` — `parse_struct_time`, `now_utc`, `parse_date`
- `app/domain/models/collected_item.py` — `tags` + `metadata` 공존
- `app/domain/services/scoring_policies.py` — `SOURCE_WEIGHTS` 부재 → silent 0점
- `tests/test_arxiv_collector_golden.py` / `test_hackernews_collector_golden.py` — 골든 모킹·필터 케이스 구조
- `app/interface/api/collect.py` — dict 레지스트리
