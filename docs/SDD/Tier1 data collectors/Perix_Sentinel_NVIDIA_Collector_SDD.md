# Perix Sentinel — NVIDIA Collector SDD

> Software Design Document · v0.1
> 목적: **origin(구 Tier1) 라인업에 NVIDIA를 추가한다.** `hardware` 도메인 첫 소스. 공식 RSS 기반, 스크래핑 리스크 없음.
> 선행: origin 9/9 소스 적재 중(arXiv·HN 포함). 후속: HF `region=cn` 태깅 / Google Research / Tier2 전환.

---

## 0. 한 줄 요약

NVIDIA 개발자 기술 블로그 RSS를 **하나의 `CollectorPort` 구현으로 추가**한다.
책임은 딱 하나 — "NVIDIA RSS 응답을 `CollectedItem` 공통 포맷으로 흘려보내기". **구현체는 `OpenAIRssCollector`의 사실상 복제**(feedparser + `parse_struct_time` + `now_utc` fallback)라 신규 인프라·유틸이 없다. 이 SDD 고유의 결정은 **① 피드 선택 ② 도메인 태그 부착 ③ 관련성 필터 여부(A0 실측으로 확정)** 3가지뿐. **스코어링은 비범위**(기존 원칙 유지).

---

## 1. 맥락: 이 작업이 큰 그림에서 어디인가

```
origin (원천)     NVIDIA ←여기, OpenAI, Anthropic, arXiv, HN, ...   "무슨 일이 일어났나"
coverage (비교군)  뉴스레터, 미디어                                  "그게 얼마나 회자되나"
        ↓ 둘 다
   공통 포맷 변환 (CollectedItem)  ←이 SDD의 작업 지점
        ↓
   스코어링 = origin 신호를 coverage corroboration으로 검증  ← 나중 (비범위)
```

NVIDIA는 **AI 인프라(하드웨어·CUDA·추론)의 1차 발생원**이다. 지금까지 origin 라인업은 `core-lab` 5개에 쏠려 있었고 `hardware` 도메인은 0개였다 — NVIDIA가 그 첫 소스다. 리서처 관점에서 CUDA·RAPIDS·추론 최적화는 매일 신경 쓰는 축이므로, "빠짐없이 깨끗한 포맷으로 받아두는 것"이 이번 작업의 전부다.

---

## 2. 목표 (Goals)

1. `NvidiaRssCollector`가 `CollectorPort` 계약을 구현하고, 단독 실행 시 **≥1건의 `CollectedItem`을 반환**한다.
2. `source="NVIDIA"`로 고정한다(§6 명명 규약).
3. RSS 응답을 **공통 포맷으로 손실 없이 정규화**한다(제목·URL·발행일·요약).
4. 기존 컬렉터와 **동일한 공통 인프라만** 사용한다: `feedparser`, `parse_struct_time`, `now_utc`, `get_logger`. **신규 유틸 0**이 목표.
5. `metadata`에 **도메인 태그**(`domain=hardware`, `region=us`, `function=origin`, `feed=developer-blog`)를 부착한다 — 미래 필터·스코어링 재료.
6. P0 규칙대로 **골든 fixture 테스트 1개**를 추가한다.

---

## 3. 비목표 (Non-Goals)

- **스코어링 일체** — `SOURCE_WEIGHTS`에 `"NVIDIA"` 키 추가, popularity 축 설계, 임계값 재보정 모두 **하지 않는다**. (Tier1↔Tier2 교차검증으로 갈아엎힐 영역)
  - ⚠️ 결과적으로 `scoring_engine._source_score`가 `SOURCE_WEIGHTS.get("NVIDIA", 0)` → **source 점수 0**. 이는 HN과 동일한 **의도된 비범위**(버그 아님). PROGRESS에 부채로만 1줄 기록.
- **다중 피드 수집** — 개발자 블로그 1개만. 공식 블로그(`blogs.nvidia.com`)·뉴스룸(`nvidianews.nvidia.com`)은 §5 참고로만 남기고 이번엔 안 붙인다.
- **HTML 폴백** — RSS 실패 시 그냥 실패로 둔다. 스크래핑 안 함.
- **태그 필드 스키마 리팩터링** — 태그는 기존 `metadata` dict에 넣는다. `CollectedItem`에 `domain`/`region` 정규 필드를 신설하는 작업은 별건(COLLECTORS.md 다음 작업 1번).
- **관련성 필터의 사전 확정** — 넣을지 말지는 A0 실측 후 결정(§7). 지금 코드로 못 박지 않는다.
- LLM 요약 — RSS `summary`를 그대로 넣는다(요약 레이어 별도).

---

## 4. RSS 계약 (Ground Truth로 확정할 것)

> ⚠️ 아래는 **설계 가정**이다. Claude Code A0에서 **실제 피드 1건을 덤프해 필드·날짜 포맷을 확정**한 뒤 파서를 고정한다(샌드박스 네트워크 제약, arXiv·HN과 동일 원칙).

- **엔드포인트**: `https://developer.nvidia.com/blog/feed` — 인증·키 불필요.
- **응답 형식**: RSS 2.0 → `feedparser`로 파싱(OpenAI 컬렉터와 동일 도구).
- **호출**: `feed = await asyncio.to_thread(feedparser.parse, RSS_URL)`, `feed.bozo` 경고 로깅(OpenAI 패턴 그대로).

### 필드 매핑 (entry → CollectedItem)

| CollectedItem | entry 출처 | 비고 |
|---|---|---|
| `source` | 고정 `"NVIDIA"` | §6 명명 규약 |
| `title` | `entry.get("title", "")` | `.strip()`. **개행/연속공백 여부 A0 확인** — 있으면 arXiv식 `_normalize` 재사용 |
| `url` | `entry.get("link", "")` | `.strip()`. `url_hash`의 입력 → 안정적 기사 URL |
| `published_at` | `entry.published_parsed` | **`parse_struct_time(...)` if 존재 else `now_utc()`** (OpenAI·arXiv 공통 fallback) |
| `summary` | `entry.get("summary", "")` | `.strip()`. 원문 그대로(요약 비범위) |
| `tags` | 고정 `["nvidia"]` (+ A0에서 category 발견 시 추가) | arXiv가 `["arxiv", "cs.ai", ...]` 한 방식과 동일 |
| `metadata` | 도메인 태그 dict | 아래 §6.2 |

### A0에서 반드시 확인할 3가지

1. **날짜 포맷** — `published_parsed`(struct_time)가 채워지는지. 채워지면 `parse_struct_time` 그대로. 안 채워지면 `entry.published`(RFC822 문자열) → `parse_date`로 폴백 경로 확정.
2. **카테고리/태그 존재** — `entry.tags`가 있으면 `tags`에 반영 + 관련성 필터의 근거로.
3. **주제 분포** — 최근 N건 중 게이밍·로보틱스 등 비-AI 비율. → **§7 필터 결정**의 데이터.

---

## 5. 피드 선택 & 볼륨 정책

### 5.1 피드 선택 (이 SDD에서 결정)

NVIDIA는 RSS가 여러 개다. **리서처 신호 밀도** 기준으로 개발자 블로그를 채택.

| 피드 | URL | 성격 | 채택 |
|---|---|---|---|
| **개발자 기술 블로그** | `developer.nvidia.com/blog/feed` | CUDA·RAPIDS·추론·연구 | ✅ **채택** |
| 공식 블로그 | `blogs.nvidia.com/feed` | 마케팅·게이밍·산업 일반 | ⬜ 미채택(노이즈↑) |
| 뉴스룸 | `nvidianews.nvidia.com/rss.xml` | 보도자료·투자 | ⬜ 미채택(코퍼릿) |

### 5.2 볼륨 정책 — 하드캡 불필요

arXiv는 API가 수백 건을 줘서 `max_results=50`으로 서버쿼리 상한을 걸었다.
**RSS는 태생적으로 유한**(보통 10~30건)이라 OpenAI 컬렉터처럼 **상한을 두지 않는다.**
- 단, A0에서 피드가 예상보다 크면(>50) 클라이언트 슬라이스 `MAX_ITEMS` 상수를 옵션으로 추가. 기본은 무제한.

---

## 6. 명명 규약 & 태그

### 6.1 source 문자열

- `source = "NVIDIA"` (대문자 고정).
- ⚠️ 나중에 `SOURCE_WEIGHTS`에 추가할 때 **키를 `"NVIDIA"`로 정확히 일치**시켜야 함(현재 dict는 `"OpenAI"`, `"Meta AI"`, `"GitHub Trending"` 식 — 표기 불일치 시 silent 0점 유지됨).

### 6.2 도메인 태그 (metadata)

기존 `tags`(flat 문자열 리스트)와 별개로, 구조화 태그는 `metadata`에 넣는다(arXiv가 authors/arxiv_id를 metadata에 넣은 방식과 동일).

```python
metadata = {
    "function": "origin",
    "domain":   "hardware",
    "region":   "us",
    "feed":     "developer-blog",
}
```

> COLLECTORS.md의 태그 체계(`function × domain × region`)와 1:1 대응. `CollectedItem` 스키마는 안 건드리므로 리스크 0.

---

## 7. 관련성 필터 — A0 결과로 분기

NVIDIA 개발자 블로그는 HN 같은 firehose는 아니지만 100% AI도 아니다(게이밍·로보틱스 혼입 가능). **필터 여부를 코드로 미리 박지 않고 A0 실측으로 결정**한다.

| A0 관측 결과 | 결정 |
|---|---|
| 비-AI 비율 **낮음(<10%)** | **필터 없음**, 전량 통과 (기본 가정) |
| 비-AI 비율 **높음** | HN 패턴 재사용 — `\b` 경계 키워드 매칭 또는 `entry.tags` 기반 제외 |

> 기본값은 **필터 없이 시작**. A0 실측이 뒤집으면 그때 HN의 `AI_KEYWORDS` 방식을 이식.

---

## 8. 절차 (A0 ~ A4)

| 단계 | 내용 |
|---|---|
| **A0 관측** | 실제 피드 덤프 → §4의 3가지 확인(날짜 포맷·태그·주제 분포) → 필드·fallback·필터 확정. 결과를 `docs/notes`에 기록 |
| **A1 파서** | `NvidiaRssCollector` 작성. `OpenAIRssCollector` 복사 후 URL·source·metadata만 교체 |
| **A2 정규화** | 제목 `.strip()`(필요 시 `_normalize`), 날짜 `parse_struct_time` fallback, metadata 태그 부착 |
| **A3 등록** | `app/interface/api/collect.py` 레지스트리에 `"nvidia": NvidiaRssCollector()` 한 줄 추가. import 추가 |
| **A4 테스트** | 골든 fixture 1개 + `/collect` 실가동 확인 |

---

## 9. 테스트 계획 (기존 골든 패턴 준수)

`test_arxiv_collector_golden.py` 구조를 그대로 따른다:

- **fixture**: `tests/fixtures/nvidia_feed.xml`(실제 RSS 스냅샷) + `tests/fixtures/nvidia_feed.golden.json`(기대 출력)
- **모킹**: `monkeypatch.setattr(feedparser, "parse", lambda _url: parsed_feed)` — **네트워크 없이** 실행
- **비교 필드**: `source / title / url / summary / tags / metadata / published_at`
- **published_at**: `.replace(tzinfo=None).isoformat()`로 aware UTC 검증(arXiv 테스트와 동일)
- **fixture 크기**: 3건 내외로 트림(PROGRESS의 fixture size 부채 원칙 준수)

---

## 10. Definition of Done

- [ ] `NvidiaRssCollector`가 `CollectorPort` 구현, 단독 실행 시 ≥1건 반환
- [ ] `source="NVIDIA"` 고정
- [ ] A0 덤프로 날짜 포맷·태그 존재·주제 분포 확정, `docs/notes`에 기록
- [ ] `published_at`이 `parse_struct_time` + `now_utc()` fallback (인라인 변환 없음)
- [ ] `tags=["nvidia"]`(+ A0 category), `metadata`에 `function/domain/region/feed` 4개 부착
- [ ] 관련성 필터 여부를 A0 근거와 함께 결정·주석화 (기본: 무필터)
- [ ] 볼륨 하드캡 없음 확인 (또는 A0 근거로 `MAX_ITEMS` 옵션 추가)
- [ ] 골든 fixture 테스트 1개 추가(3건 내외), 전체 테스트 그린
- [ ] `collect.py` 레지스트리 등록 + import, `/collect` 실가동 DB 적재 확인
- [ ] **스코어링 파일 무수정** (`SOURCE_WEIGHTS`·`scoring_engine`·`scoring_policies` 손대지 않음)
- [ ] PROGRESS에 "NVIDIA source 점수 0 — 의도된 비범위, Tier2 재보정 시 처리" 1줄 기록
- [ ] 신규 유틸 추가 0 확인 (있었다면 사유 기록)

---

## 부록: 참고한 실제 코드

- `app/infrastructure/collectors/openai_rss_collector.py` — 복사 기반(가장 가까운 형제)
- `app/infrastructure/collectors/arxiv_api_collector.py` — `_normalize`·metadata·tags 패턴
- `app/core/datetime_utils.py` — `parse_struct_time`(struct_time→aware UTC), `now_utc`, `parse_date`(문자열 폴백용)
- `app/domain/models/collected_item.py` — `tags: list[str]` + `metadata: dict` 공존 확인
- `app/domain/services/scoring_policies.py` — `SOURCE_WEIGHTS`에 NVIDIA 부재 → silent 0점 확인
- `tests/test_arxiv_collector_golden.py` — 골든 테스트 모킹·비교 구조
- `app/interface/api/collect.py` — dict 레지스트리(한 줄 추가 지점)
