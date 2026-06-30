# Perix Sentinel — Hacker News Collector SDD

> Software Design Document · v0.1
> 목적: **Tier 1(원천) 소스에 Hacker News를 추가한다.** 공식 Firebase API 기반, 스크래핑 리스크 없음.
> 선행: arXiv 컬렉터 완료(8/8 소스 적재 중). 후속: Tier2(뉴스레터·미디어) 또는 P2.

---

## 0. 한 줄 요약

HN을 **하나의 `CollectorPort` 구현으로 추가**한다. arXiv와 동일한 A0~A4 절차를 재사용하되, HN 고유의 **3가지 차이**(2단계 호출 · epoch 시간 · AI 관련성 필터)를 A0에서 먼저 못 박는다. **스코어링은 비범위**(arXiv와 동일 원칙).

---

## 1. 맥락: arXiv와 무엇이 다른가

arXiv는 `cat:cs.AI` 쿼리만으로 **이미 주제가 걸러진** 데이터였다. HN은 다르다 — **일반 테크 뉴스 firehose**라, 받아오는 순간엔 AI와 무관한 글(스타트업·하드웨어·정치·HN 메타글)이 대부분이다. 따라서 HN 컬렉터의 핵심 난제는 파싱이 아니라 **"무엇을 신호로 남길 것인가(필터링)"**다.

| 축 | arXiv | Hacker News |
|---|---|---|
| 호출 횟수 | **1회** (피드 한 방) | **2단계** (topstories → item별 N회) |
| 시간 포맷 | ISO8601 문자열 (`published`) | **Unix epoch 정수** (`time`) |
| 응답 형식 | Atom XML (`feedparser`) | **JSON** (`fetch_json`) |
| 주제 사전 필터 | 쿼리(`cat:`)로 해결됨 | **없음 → 컬렉터가 직접 필터** |
| 인기 신호 | 없음 | `score`(points), `descendants`(댓글수) 존재 |

> 정리: HN은 **인프라는 더 단순**(JSON)하지만 **정책 결정은 더 많다**(필터·볼륨·시간변환).

---

## 2. 목표 (Goals)

1. `HackerNewsApiCollector`가 `CollectorPort`를 구현하고, 단독 실행 시 **AI 관련 story ≥1건**을 `CollectedItem`으로 반환한다.
2. **2단계 호출**(topstories ID 리스트 → item 상세)을 공통 `fetch_json`으로 처리한다.
3. **epoch → aware UTC** 변환을 공통 datetime 레이어로 흡수한다(인라인 변환 금지, §6.2 참조).
4. **AI 관련성 필터 + 볼륨 상한**을 컬렉터 단에서 명시적으로 통제한다.
5. P0 규칙대로 **골든 fixture 테스트 1개**를 추가한다.

## 3. 비목표 (Non-Goals)

- **스코어링 일체** — `SOURCE_WEIGHTS`에 HN 추가, points/comments를 popularity 축에 반영, 임계값 재보정 모두 **하지 않는다**. (Tier1↔Tier2 교차검증에서 별도 설계)
  - ⚠️ 단, HN의 `score`/`descendants`는 **나중 popularity 설계의 1순위 재료**이므로 `metadata`에 **반드시 보존**한다(버리지 말 것).
- 댓글(comment) 본문 수집 / `kids` 트리 순회 — story 메타데이터까지만.
- Algolia HN Search API(과거 검색용) — 우리는 실시간 firehose만 필요.
- Ask/Show/Job 스토리 별도 엔드포인트 — MVP는 `topstories`만(추후 확장 여지).

---

## 4. HN Firebase API 계약 (A0에서 관측 확정)

> ⚠️ 아래는 설계 가정. Claude Code A0에서 **실제 응답 1건을 덤프**해 필드·타입을 고정한 뒤 파서를 박는다(arXiv와 동일 원칙).

- **베이스**: `https://hacker-news.firebaseio.com/v0/` — 인증·키 불필요, 명시된 레이트리밋 없음(매너 throttle 권장).
- **1단계**: `GET /v0/topstories.json` → **item ID 정수 배열**(최대 500, jobs 포함).
- **2단계**: `GET /v0/item/{id}.json` → 단일 item 객체.

### item 객체 필드 (가정)

| 필드 | 타입 | 비고 |
|---|---|---|
| `id` | int | item 고유 ID |
| `type` | str | `story`/`comment`/`job`/`poll`/`pollopt` → **`story`만 통과** |
| `by` | str | 작성자 |
| `time` | int | **Unix epoch (초)** → aware UTC 변환 대상 |
| `title` | str | 제목 (HTML 가능 → 정규화) |
| `url` | str | **외부 기사 URL (옵션!)** — Ask/Show HN 등 self-post엔 없음 (§6.3) |
| `score` | int | points (인기 신호 → metadata 보존) |
| `descendants` | int | 총 댓글수 (인기 신호 → metadata 보존) |
| `kids` | int[] | 댓글 ID 배열 (수집 안 함) |

### 필드 매핑 (HN item → CollectedItem)

| CollectedItem | HN 출처 | 비고 |
|---|---|---|
| `source` | 고정 `"Hacker News"` | §6.1 명명 규약 |
| `title` | `item.title` | HTML 엔티티·개행 정규화 |
| `url` | `item.url` **또는** HN 토론 링크 | **§6.3 핵심 결정** — url 없을 때 fallback |
| `published_at` | `item.time` (epoch) | **§6.2 epoch 변환** |
| `summary` | (story엔 본문 없음) | 빈 문자열 또는 `text`(Ask HN만 존재) |
| `tags` | `["hackernews", type, ...AI키워드]` | 필터에 쓴 키워드를 태그로도 |
| `metadata` | `score`, `descendants`, `by`, `hn_id`, `type` | **인기 신호 반드시 보존** |

---

## 5. 필터 & 볼륨 정책 (이 SDD의 핵심 결정)

HN은 firehose라 정책이 곧 품질이다.

| 항목 | 제안 기본값 | 근거 |
|---|---|---|
| 1단계 상한 | topstories 상위 `N_TOP = 100`개 ID만 | 500 전부 fetch는 과함. front page 상위가 신호 밀도 높음 |
| type 필터 | `story`만 (job/poll 제외) | 원천 신호는 story |
| **AI 관련성 필터** | title에 AI 키워드 매칭 | **firehose → 신호 변환의 핵심** |
| 최종 건수 | 필터 통과분 전체 (상한 N_TOP 내) | 자연스럽게 소량만 남음 |

### AI 관련성 필터 — 결정 필요 (§6.4)

topstories 100개 중 AI 글은 보통 한 줌이다. **title 기준 키워드 매칭**을 1차안으로 제안:

```
AI_KEYWORDS = ["ai", "llm", "gpt", "claude", "gemini", "agent", "rag",
               "model", "neural", "ml", "diffusion", "transformer",
               "openai", "anthropic", "deepmind", ...]
```

- **장점**: 단순·빠름·결정적(테스트 쉬움).
- **리스크**: `"ai"` 부분매칭 오탐("**ai**rport", "f**ai**l", "ch**ai**n"). → **단어 경계(`\bai\b`) 매칭**으로 완화.
- **대안**: 기존 `scoring_policies.KEYWORD_WEIGHTS` 키 재사용 → 일관성↑. 단 그건 스코어링 자산이라, **수집 필터가 스코어링에 의존하면 비범위 경계가 흐려짐**. → MVP는 컬렉터 자체 상수 권장.

> ⚠️ **2단계 호출 비용과 필터 순서**: title 필터를 **언제** 적용하느냐가 호출 수를 좌우한다. topstories는 ID만 주므로 title을 보려면 item을 fetch해야 함 → **N_TOP개를 일단 다 fetch한 뒤 title 필터**가 불가피(arXiv의 "ranking은 LLM 앞" 원칙과 유사하게, 여기선 "필터는 fetch 뒤"가 구조적 제약). N_TOP을 100으로 잡은 이유가 이 비용 통제.

---

## 6. 결정해야 할 것 (Open Decisions)

> A1 들어가기 전에 못 박으면 깔끔한 지점들.

1. **`source` 명명** — `"Hacker News"` vs `"HackerNews"` vs `"HN"`.
   - 권고: **`"Hacker News"`** (사람이 읽는 표기, 기존 `"GitHub Trending"`·`"Mistral AI"`와 톤 일치).
2. **epoch 변환 위치** — `datetime_utils`에 **공통 함수 신설** vs 컬렉터 인라인.
   - 권고: **`datetime_utils`에 `from_epoch(ts: int) -> datetime` 신설**. 이유: 인라인 변환은 arXiv에서 경계했던 "공통 레이어 우회"이고, HN 외 다른 epoch 소스(Reddit 등) 추가 시 재사용됨. **이건 R3 공통화 정신의 연장이라 비범위 위반 아님**(scoring 무관).
3. **url 없는 story 처리** — Ask/Show HN, self-post는 `item.url`이 없음.
   - 옵션 A: **HN 토론 링크로 fallback** (`https://news.ycombinator.com/item?id={id}`) — 항상 존재, `url_hash` 안정.
   - 옵션 B: url 없으면 **스킵**.
   - 권고: **A** — 원천 신호는 "HN에서 회자됨" 자체가 의미. 토론 링크가 정답.
4. **AI 필터 키워드 출처** — 컬렉터 자체 상수(권고) vs `KEYWORD_WEIGHTS` 재사용(§5 참조).
5. **단어 경계 매칭** — 짧은 키워드(`ai`, `ml`, `rag`) 오탐 방지로 `\b` 적용할지. 권고: **적용**.

---

## 7. 작업 계획 (Phased)

브랜치: `feat/hackernews-collector`. 각 단계 독립 커밋.

| Phase | 내용 | DoD |
|---|---|---|
| **A0** | topstories + item 각 1건 실제 응답 덤프 → §4 필드·타입 확정, §6 결정 확정 | epoch 값·url 유무·필드 키 기록 |
| **A1** | `HackerNewsApiCollector` 구현 (2단계 fetch + epoch 변환 + AI 필터 + 볼륨 상한) | 단독 실행 시 AI story ≥1건 |
| **A1.5** | `datetime_utils.from_epoch()` 신설 + 단위 테스트 | epoch→aware UTC 검증 |
| **A2** | `collect.py` 레지스트리에 `"hackernews"` 한 줄 추가 | `/collect`에 HN 포함 |
| **A3** | 골든 fixture 테스트 1개 (topstories+item JSON 박제 → 필터·파싱 검증) | 테스트 그린 |
| **A4** | `/collect` 1회 실가동 → DB에 HN row 적재 확인 | DB count(Hacker News) > 0 |

> A0에서 **반드시 확인할 것 2개**: (a) `time`이 epoch 초가 맞는지(밀리초 아님), (b) 상위 100개 중 `url` 없는 story 비율(§6.3 fallback 필요성 가늠).

> A3 골든 테스트의 모킹 포인트: `fetch_json`이 **호출 인자(URL)에 따라 다른 응답**을 줘야 함(topstories면 ID 배열, item이면 item 객체). arXiv의 단일 모킹보다 한 단계 복잡 → URL 분기 모킹 헬퍼 필요.

---

## 8. 완료 정의 (DoD)

- [ ] `HackerNewsApiCollector.collect()`가 AI 관련 story ≥1건 반환
- [ ] 2단계 호출이 공통 `fetch_json` 경유 (직접 httpx 사용 0건)
- [ ] epoch 변환이 `datetime_utils.from_epoch()` 공통 함수 경유 (인라인 변환 0건)
- [ ] `title` HTML 엔티티·개행 정규화 적용
- [ ] AI 필터·`N_TOP` 상한이 모듈 상수로 명시
- [ ] `url` 없는 story가 HN 토론 링크로 fallback (§6.3 A안 채택 시)
- [ ] `score`·`descendants`가 `metadata`에 보존됨 (나중 popularity 재료)
- [ ] `source="Hacker News"`로 고정
- [ ] `collect.py` 등록, `/collect` 응답에 `"hackernews"` 키 존재
- [ ] 골든 fixture 테스트 1개 그린
- [ ] `/collect` 실가동 후 DB에 HN 소스 row 존재
- [ ] **스코어링 파일(`scoring_policies.py`, `scoring_engine.py`) 무변경** ← 비범위 준수

---

## 9. 리스크 & 완화

- **2단계 호출 폭주** → `N_TOP=100` 상한 필수. 매너 throttle(순차 또는 소량 동시성). 명시 레이트리밋은 없지만 과다 요청 시 IP 차단 가능 → 공통 `fetch_json`의 재시도/백오프에 의존하되, 동시성은 보수적으로.
- **epoch 단위 오해(초 vs 밀리초)** → A0에서 실제 값 확인 후 `from_epoch` 고정. (HN은 초 단위지만 관측으로 못 박기)
- **AI 필터 오탐/누락** → `\b` 단어경계 + title 기준. fixture 테스트에 "통과해야 할 글 / 걸러야 할 글" 양쪽 케이스 포함.
- **url 없는 self-post** → §6.3 fallback으로 `url_hash` 안정성 확보.
- **silent date fallback(공통 부채)** → epoch는 파싱 실패 여지가 적지만, `time` 누락 item은 `now_utc()`로 흐름. A0에서 누락 빈도 확인.
- **점수 0으로 보일 것** → HN이 `SOURCE_WEIGHTS`에 없어 source 0점. **버그 아님, 의도된 비범위**임을 PROGRESS에 명시.

---

## 10. 다음 연결 (이 SDD 이후)

HN 완료 → **Tier1 원천 라인업 일단락**(arXiv·HN까지 안정 API 소스 확보).
다음 갈림길:
- **Tier2(뉴스레터·미디어) 수집** — 비교군 데이터. 그래야 스코어링 재설계의 재료가 모임.
- 또는 보류 중인 **P2(BaseHtmlCollector)** — HTML 컬렉터 5개 슬림화.

그 다음에야 **스코어링을 Tier1↔Tier2 교차검증으로 재설계**(HN의 `score`/`descendants`가 여기서 popularity 재료로 부활).
