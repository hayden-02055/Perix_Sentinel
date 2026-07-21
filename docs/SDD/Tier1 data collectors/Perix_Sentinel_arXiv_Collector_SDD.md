# Perix Sentinel — arXiv Collector SDD

> Software Design Document · v0.1
> 목적: **Tier 1(원천) 소스에 arXiv를 추가한다.** 공식 API 기반, 스크래핑 리스크 없음.
> 선행: Collector Revival 완료(7/7 소스 적재 중). 후속: Hacker News 컬렉터(별도 SDD).

---

## 0. 한 줄 요약

arXiv를 **하나의 `CollectorPort` 구현으로 추가**한다. 책임은 딱 하나 — "arXiv API 응답을 `CollectedItem` 공통 포맷으로 흘려보내기". **스코어링·가중치·인기 신호는 이 SDD의 범위가 아니다**(Tier1↔Tier2 교차검증 단계에서 별도 설계).

---

## 1. 맥락: 이 작업이 큰 그림에서 어디인가

```
Tier 1 (원천)        arXiv ←여기,  HN, OpenAI, Anthropic, ...   "무슨 일이 일어났나"
Tier 2 (비교군)      뉴스레터, 미디어                            "그게 얼마나 회자되나"
        ↓ 둘 다
   공통 포맷 변환 (CollectedItem)  ←이 SDD의 작업 지점
        ↓
   스코어링 = Tier1 신호를 Tier2 corroboration으로 검증   ← 나중 (비범위)
```

arXiv는 **AI 연구의 1차 발생원**이다. 논문이 arXiv에 올라오는 순간이 신호의 출발점이고, 그게 뉴스레터·미디어(Tier2)에서 회자되는지가 나중에 중요도를 결정한다. 따라서 이번엔 **"빠짐없이, 깨끗한 포맷으로 받아두는 것"**이 전부다.

---

## 2. 목표 (Goals)

1. `ArxivApiCollector`가 `CollectorPort` 계약을 구현하고, 단독 실행 시 **≥1건의 `CollectedItem`을 반환**한다.
2. arXiv Atom 응답을 **공통 포맷으로 손실 없이 정규화**한다(제목·요약·발행일·저자·카테고리·URL).
3. **볼륨 제어**: 카테고리·건수 상한을 컬렉터 단에서 명시적으로 통제한다(arXiv는 하루 수백 건이라 무제한 수집 시 DB 도배).
4. 기존 컬렉터와 동일한 **공통 인프라**(`fetch_*`, `parse_date`, `now_utc`)만 사용한다.
5. P0 규칙대로 **골든 fixture 테스트 1개**를 추가한다.

## 3. 비목표 (Non-Goals)

- **스코어링 일체** — `SOURCE_WEIGHTS`에 arXiv 키 추가, popularity 축 설계, 임계값 재보정 모두 **하지 않는다**. (어차피 Tier1↔Tier2 교차검증으로 갈아엎힐 영역)
- Hacker News 컬렉터 — 다음 SDD.
- 레지스트리 추상화(`collect.py`의 dict → 동적 등록) — 지금은 dict에 한 줄 추가로 충분.
- 저자/카테고리 기반 고급 필터, 중복 논문(v1/v2) 병합, full-text 수집.
- LLM 요약 — arXiv abstract를 그대로 `summary`에 넣는다(요약 레이어는 별도).

---

## 4. arXiv API 계약 (Ground Truth로 확정할 것)

> ⚠️ 아래는 **설계 가정**이다. Claude Code에서 첫 구현 시 **실제 응답 1건을 덤프해 필드를 확정**한 뒤 파서를 고정한다(샌드박스 네트워크 제약으로 라이브 검증 미수행).

- **엔드포인트**: `http://export.arxiv.org/api/query`
- **응답 형식**: **Atom XML**(JSON 아님). → `feedparser`로 파싱(OpenAI RSS 컬렉터와 동일 도구 재사용 가능).
- **쿼리 파라미터**:
  - `search_query` — 예: `cat:cs.AI OR cat:cs.CL OR cat:cs.LG`
  - `sortBy=submittedDate`, `sortOrder=descending` — 최신순(원천 신호엔 필수)
  - `start=0`, `max_results=N` — 볼륨 상한
- **엔트리 필드(가정)**: `id`(논문 URL/abs 링크), `title`, `summary`(abstract), `published`, `updated`, `authors[].name`, `arxiv_primarycategory` 또는 `tags`(카테고리), `link`(abs/pdf).

### 필드 매핑 (arXiv entry → CollectedItem)

| CollectedItem | arXiv 출처 | 비고 |
|---|---|---|
| `source` | 고정 문자열 | **§6 명명 규약 참조** |
| `title` | `entry.title` | 개행/연속공백 정규화 필요(arXiv title은 줄바꿈 포함) |
| `url` | `entry.id` 또는 abs 링크 | `url_hash`의 입력 → **안정적인 abs URL로 고정**(pdf 링크 X) |
| `published_at` | `entry.published` | `parse_struct_time(published_parsed)` 또는 `parse_date` |
| `summary` | `entry.summary` (abstract) | 개행 정규화. 원문 그대로(요약 비범위) |
| `tags` | primary/secondary category | `["arxiv", "cs.ai", ...]` 형태 |
| `metadata` | authors, primary_category, arxiv_id, comment | 구조화 보존(나중 Tier2 매칭용) |

---

## 5. 볼륨 제어 정책 (이 SDD에서 결정할 것)

arXiv는 무제한이면 위험하다. 컬렉터 상수로 못 박는다.

| 항목 | 제안 기본값 | 근거 |
|---|---|---|
| 카테고리 | `cs.AI`, `cs.CL`, `cs.LG` | AI 핵심 3종. 필요 시 `cs.CV`, `stat.ML` 추가 |
| 정렬 | 최신 제출순 | 원천 신호는 "방금 올라온 것"이 핵심 |
| 1회 상한 | `max_results = 50` | 하루 1~2회 수집 가정 시 충분, DB 도배 방지 |
| 기간 | (선택) 최근 N일만 | API 정렬+상한으로 사실상 대체 가능 → MVP에선 생략 가능 |

> 정책은 **컬렉터 모듈 상단 상수**로 둬서 한눈에 보이고 바꾸기 쉽게. 스코어링에 떠넘기지 않는다(점수는 비범위이고, 애초에 양 제어는 수집 단 책임).

---

## 6. 결정해야 할 것 (Open Decisions)

> 큰 흐름엔 영향 없지만, 첫 구현 전에 못 박으면 깔끔한 지점들.

1. **`source` 명명 규약** — 기존 소스는 `source` 문자열이 **스코어링 join 키**다(`SOURCE_WEIGHTS.get(item.source)`). 지금은 점수가 비범위라 무가중(0점)으로 흘러도 무방하지만, **나중에 일관성이 깨지지 않도록 canonical 이름을 지금 고정**하자.
   - 후보: `"arXiv"` (← 추천, 표기 일관) vs `"arXiv cs.AI"`(카테고리 분리) vs `"ArXiv"`.
   - 권고: **`"arXiv"` 단일** — 카테고리는 `tags`/`metadata`에 보존.
2. **파싱 도구** — `feedparser`(OpenAI 패턴 그대로) vs `xml.etree`(의존성 최소). 권고: **`feedparser`** — 이미 의존성에 있고 검증된 패턴.
3. **`url` 안정성** — arXiv는 같은 논문이 `abs`/`pdf`/버전(`v1`,`v2`) URL을 가짐. `url_hash` 중복 판정이 흔들리지 않도록 **버전 없는 abs URL로 정규화**할지 결정(권고: 정규화하여 v업데이트를 같은 항목으로 볼지 / 별개로 볼지 — MVP에선 **API가 준 id 그대로**도 허용).

---

## 7. 작업 계획 (Phased)

브랜치: `feat/arxiv-collector`. 각 단계 독립 커밋.

| Phase | 내용 | DoD |
|---|---|---|
| **A0** | API 응답 1건 덤프 → §4 필드 확정, §6 결정 확정 | 실제 엔트리 키 목록 기록 |
| **A1** | `ArxivApiCollector` 구현 (feedparser + §5 볼륨 상수) | 단독 실행 시 ≥1건 반환 |
| **A2** | `collect.py` 레지스트리 dict에 `"arxiv"` 한 줄 추가 | `/collect`에 arXiv 포함 |
| **A3** | 골든 fixture 테스트 1개 (응답 XML 박제 → N건 파싱 검증) | 테스트 그린 |
| **A4** | `/collect` 1회 실가동 → DB에 arXiv row 적재 확인 | DB count(arXiv) > 0 |

> A0를 분리한 이유: arXiv Atom 필드명(`feedparser`가 정규화하는 키)이 가정과 다를 수 있어, **파서를 박제하기 전에 1회 관측**한다(Mistral에서 가정 깨졌던 교훈).

---

## 8. 완료 정의 (DoD)

- [ ] `ArxivApiCollector.collect()`가 단독 실행 시 `list[CollectedItem]` ≥1건 반환
- [ ] `title`/`summary` 개행·연속공백 정규화 적용
- [ ] 카테고리·`max_results` 상한이 모듈 상수로 명시
- [ ] `source="arXiv"`(또는 §6에서 합의한 값)로 고정
- [ ] `collect.py`에 등록, `/collect` 응답에 `"arxiv"` 키 존재
- [ ] 골든 fixture 테스트 1개 그린
- [ ] `/collect` 실가동 후 DB에 arXiv 소스 row 존재
- [ ] **스코어링 관련 파일(`scoring_policies.py`, `scoring_engine.py`) 무변경** ← 비범위 준수 확인

---

## 9. 리스크 & 완화

- **Atom 필드 가정 오류** → A0에서 1회 관측 후 박제. 가정만으로 파서 고정 금지.
- **볼륨 폭주** → `max_results` 상한 필수. 카테고리도 좁게 시작.
- **`url_hash` 불안정(버전/abs/pdf)** → §6.3에서 URL 정규화 정책 확정 후 일관 적용.
- **silent date fallback(공통 부채)** → `parse_date` 실패 시 `now_utc()`로 조용히 흐르는 기존 부채가 arXiv에도 적용됨. **이 SDD에서 새로 고치진 않되**, A0에서 published 파싱이 실제로 되는지만 눈으로 확인.
- **점수 0으로 보일 것** → arXiv가 `SOURCE_WEIGHTS`에 없어 source 점수 0. **이건 버그가 아니라 의도된 비범위**임을 PROGRESS에 명시(다음 사람이 "고쳐야 하나?" 헷갈리지 않게).

---

## 10. 다음 연결 (이 SDD 이후)

arXiv 완료 → **Hacker News 컬렉터**(별도 SDD, 같은 절차 A0~A4 재사용).
Tier1이 충분해지면 → **Tier2(뉴스레터·미디어) 수집** → 그 다음에야 **스코어링을 Tier1↔Tier2 교차검증으로 재설계**.
