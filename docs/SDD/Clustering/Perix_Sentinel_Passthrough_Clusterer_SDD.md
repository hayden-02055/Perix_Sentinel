# Perix Sentinel — Passthrough Clusterer SDD

> Software Design Document · v0.1
> 목적: **임계값이 필요 없는 부분만 지금 지어서 파이프라인을 end-to-end로 검증한다.**
> 대상: Claude Code 구현 위임용. **A0 관측을 먼저 수행하고, 그 결과에 근거해 A1~A4를 구현할 것.**
> 전제: origin↔origin / origin↔coverage 두 축 실측 완료 (§1 참조).

---

## 0. 한 줄 요약

`list[CollectedItem] → list[Event]`를 반환하는 **소스 무관(source-agnostic) 클러스터러**를 만들되, 병합 규칙은 **정확 중복(canonical URL 일치)만** 적용한다. 나머지는 1-item Event로 그대로 통과시킨다. 기존 `clusterer.py`의 퍼지 로직(시간창 gate1, jaccard, org overlap)은 **삭제하지 않고 비활성·격리**하여 폴리싱 단계 슬롯으로 남긴다.

---

## 1. 배경 근거 (왜 퍼지가 아니라 패스스루인가)

두 축 모두 실측했고, 자동 퍼지 병합의 실증 근거가 **없음**을 두 번 확인했다. 이 결정은 추측이 아니라 데이터 기반이다.

| 축 | 프로덕션 시간창 결과 | 함의 |
|---|---|---|
| origin ↔ origin | 1,585건 중 **1쌍 (0.06%)** — 콤마 버그 수정 후에도 동일, 측정 아티팩트 아님 | 임계값을 잡을 양성 표본 부족 |
| origin ↔ coverage (TechCrunch 20건) | **0쌍 (0%)** — gate1(-6h/+48h) 통과 후보 전무 | 검증 대상 자체가 없음 |

추가 확정 사항:
- **Jaccard는 1차 게이트로 부적격.** 유일 진짜 양성이 최저 jaccard(0.20), 최고 jaccard(0.27)가 가짜. jaccard는 org+시간창의 보조 신호일 뿐.
- **0%의 원인은 구조적**이다: (a) coverage 볼륨 20건, (b) TechCrunch에 오피니언/칼럼 혼재(특정 origin 사건을 echo하지 않음), (c) org overlap이 coverage에 최악(칼럼 1건이 org명만으로 origin 아카이브 1,059건과 무차별 매칭).
- 따라서 **퍼지 매칭 검증은 본질적으로 폴리싱 단계 작업**이다. coverage 5개 소스가 수 주간 상시 운영돼야 유의미한 echo 쌍이 쌓인다.

→ 지금 임계값이 들어가는 어떤 병합도 검증 불가능한 추측이 된다. **임계값 없는 정확 중복만** 지금 구현하고, 파이프라인 배선을 검증한다.

---

## 2. 목표 (Goals)

1. **소스 무관 클러스터러 인터페이스 확립** — `Clusterer.cluster(items: list[CollectedItem]) -> list[Event]`. origin/coverage 구분을 로직에 하드코딩하지 않는다.
2. **정확 중복 병합** — canonical URL(정규화 후)이 같은 아이템만 하나의 Event로 병합. 결정론적.
3. **패스스루** — 병합 대상이 없는 아이템은 `source_count=1`인 1-item Event로 통과.
4. **Event 도메인 모델 확립** — `source_count`, `source_diversity`, `first_seen` 등 증폭 신호 필드의 자리를 마련(지금은 대부분 1).
5. **파이프라인 end-to-end 배선** — 저장된 아이템 → 클러스터(패스스루) → Event → 브리핑까지 실제로 완주 검증.
6. **퍼지 슬롯 보존** — 기존 퍼지 로직을 삭제하지 않고 비활성·격리하여 폴리싱 단계 교체 지점으로 남긴다.

---

## 3. 비목표 (Non-Goals) — 명시적 스코프 경계

아래는 **이번 페이즈에서 하지 않는다.** 대부분 폴리싱 단계로 이관하며 §11 PROGRESS.md 갱신에 근거와 함께 기록한다.

- ❌ **퍼지/유사도 매칭 활성화** — 시간창 gate1(-6h/+48h), jaccard, org overlap 병합. → 폴리싱
- ❌ **origin ↔ coverage 매칭** — 실증 근거 없음(0%). → coverage 5개 상시 운영 후 재측정
- ❌ **SimilarityPort / 임베딩 구현** — 인터페이스 문서화만, 구현 없음. → 폴리싱
- ❌ **Event DB 영속화(별도 `events` 테이블)** — MVP는 브리핑 경로에서 **in-memory 계산**. 영속화는 필요성 확인 후 별도 작업.
- ❌ **스코어링 파일 수정** — `scoring_engine`, `SOURCE_WEIGHTS` 등 완전 무수정. `source_count` 반영은 다음 단계.
- ❌ **스케줄러(APScheduler)** — 별도 페이즈.
- ❌ **기존 퍼지 로직 삭제** — 비활성만. 코드는 남긴다.

> **원칙: 이 SDD의 모든 병합은 결정론적이어야 한다. 임계값이 등장하면 그것은 비목표 위반이다.**

---

## 4. 클러스터러 고유 이슈 (Clusterer-Specific Issues)

기존 컬렉터 SDD와 달리 이 작업은 **외부 소스가 없고**, 이슈는 전부 내부 도메인 로직에 있다.

- **I1. 대표 아이템(primary) 선정** — 병합된 Event의 title/url을 무엇으로 할 것인가. 소스 무관 원칙상 origin 우선 같은 functional-axis 규칙을 쓰면 안 됨. → **가장 이른 `published_at`** 기준, 동률 시 안정적 tiebreak(예: source 이름 알파벳순).
- **I2. URL 정규화** — 같은 사건인데 tracking 파라미터(utm_*, ref 등)·trailing slash·host 대소문자 차이로 canonical key가 갈리면 정확 중복을 놓친다. 정규화 규칙 필요.
- **I3. URL 없는 아이템** — 일부 origin(예: HN self-post는 discussion 링크 fallback)이나 title-only 케이스. canonical key를 URL로 못 잡으면 title 정규화 fallback.
- **I4. `source_diversity` 정의 모호** — distinct `source`(컬렉터명)인가 distinct `domain`(core-lab/hardware/...)인가. → **둘 다 다르니 명확히 고정**: `source_count` = distinct source 수, `source_diversity` = distinct domain 수. A0에서 실제 필드명 확인.
- **I5. 기존 퍼지 로직과의 공존** — `clusterer.py`에 이미 gate1/jaccard/org가 있음. 활성 경로를 ExactDup으로 교체하되 퍼지를 남겨야 함. A0가 현재 구조를 먼저 파악해야 리팩터 방식이 정해짐.

---

## 5. Event 모델 계약 (Event Model Contract)

> **A0 확인 필수**: 아래 필드/타입은 설계 의도이며, `CollectedItem`의 **실제 필드명**(특히 URL·timestamp 필드명)에 맞춰 A0에서 확정할 것.

```
Event
├─ event_id: str          # canonical_key 기반 안정적 해시 (결정론적)
├─ canonical_url: str|None # 정규화된 대표 URL
├─ title: str             # primary_item의 title
├─ items: list[CollectedItem]  # 멤버 (패스스루면 길이 1)
├─ primary_item: CollectedItem # 가장 이른 published_at (I1)
├─ source_count: int      # len(distinct item.source)
├─ source_diversity: int  # len(distinct item.domain)  ← I4
├─ sources: list[str]     # distinct source 이름
├─ domains: list[str]     # distinct domain
├─ regions: list[str]     # distinct region
├─ first_seen: datetime   # min(published_at)
└─ last_seen: datetime    # max(published_at)
```

**병합 규칙 (결정론적, 임계값 없음)**
```
canonical_key(item) =
    normalize_url(item.url)  if item.url present
    else  "title:" + normalize_title(item.title)

같은 canonical_key → 하나의 Event로 병합
그 외 → 각각 1-item Event
```

**normalize_url 규칙 (I2)**
- scheme+host 소문자화
- trailing slash 제거
- fragment(`#...`) 제거
- tracking 쿼리 파라미터 제거: `utm_*`, `ref`, `source`, `fbclid` 등 (화이트리스트가 아니라 블랙리스트로, 의미 있는 쿼리는 보존)
- A0에서 기존 URL 정규화 유틸 존재 여부 확인 후 재사용 or 신규

---

## 6. 명명 규칙 (Naming Conventions)

- 도메인 서비스: `app/domain/services/clusterer.py` (기존 파일 활용)
- 활성 구현 클래스: `ExactDupClusterer` (또는 A0에서 확인한 기존 네이밍 관습에 맞춤)
- 포트(있다면): `app/domain/ports/clusterer_port.py` → `ClustererPort.cluster(items) -> list[Event]`
- Event 모델: `app/domain/models/event.py` (없으면 신규, 있으면 확장)
- 비활성 퍼지: 기존 함수는 `_legacy_fuzzy_*` 접두 또는 별도 `FuzzyClusterer` 클래스로 격리 (A0 구조에 따라 결정)
- A0 노트: `docs/notes/clusterer-passthrough-a0.md`

---

## 7. A0 — 관측 단계 (코드 수정 금지, 읽기 전용)

> **이 단계 없이 A1로 넘어가지 말 것.** 아래 질문에 실제 코드를 읽고 답한 뒤 `docs/notes/clusterer-passthrough-a0.md`에 기록한다. 이 노트가 A1~A4의 근거가 된다.

**Q1. `app/domain/services/clusterer.py` 현재 구조**
- 진입 함수 시그니처는? 반환 타입이 이미 Event인가, dict인가, list인가?
- gate1 상수(-6h/+48h) 위치와 사용처
- jaccard 계산 함수, org overlap 로직의 위치
- 이 파일이 현재 파이프라인에서 **실제로 호출되고 있는가**, 아니면 미배선 스캐폴딩인가?

**Q2. Event/Cluster 모델 존재 여부**
- `app/domain/models/`에 event/cluster 모델이 이미 있나? 있으면 필드는?
- 없으면 신규 생성. `CollectedItem`과의 조합 관계 확인.

**Q3. `CollectedItem` 실제 필드 확정**
- URL 필드명 정확히 (`url`? `link`?)
- timestamp 필드명 (`published_at`? `published`? `date`?)
- `source`, `domain`, `region`, `tags: list[str]`, `metadata: dict` 존재 확인

**Q4. `entity_extractor.py`**
- `tokenize()` 콤마 버그 수정 반영 확인 (이미 수정됨)
- org 추출 함수 시그니처 (퍼지 격리 시 유지 대상)

**Q5. 브리핑/파이프라인 배선 지점**
- 현재 브리핑이 **아이템 단위**인가? `CollectTrendsUseCase`가 collect 시점에 per-item 스코어링+발행하는 구조인가?
- 저장된 아이템을 다시 읽는 경로(repository 쿼리)가 있나?
- 클러스터러를 끼울 **가장 덜 침습적인 지점**은 어디인가?

**Q6. 포트/유틸 존재 확인**
- `domain/ports`에 ClustererPort 유사 포트가 있나?
- URL 정규화 유틸이 이미 어딘가 있나?

**Q7. 기존 테스트**
- clusterer 관련 골든/픽스처가 있나? 재사용 가능한가?

**A0 산출물**: 위 답변 기록 + "무엇을 비활성/격리하고 무엇을 신규 생성하는가"의 1문단 요약.

---

## 8. A1~A4 — 구현 단계

> A0 결과에 근거해 진행. A0에서 발견한 실제 구조가 이 SDD의 가정과 다르면, **SDD 가정이 아니라 실제 코드를 따르고** A0 노트에 불일치를 기록한다.

**A1. Event 모델 정의/확장**
- §5 계약대로. A0 Q2/Q3 결과에 맞춰 필드명 확정.
- `first_seen`/`last_seen`/`source_count`/`source_diversity` 계산 로직 포함(대부분 1이어도 정확히).

**A2. ExactDupClusterer 구현 + 퍼지 격리**
- `cluster(items) -> list[Event]` 구현: canonical_key로 그룹핑 → Event 생성.
- `normalize_url`(§5) 구현 or 기존 유틸 재사용.
- 기존 gate1/jaccard/org 로직을 **삭제 없이 비활성·격리** (A0 Q1 구조에 따라 `_legacy_*` 접두 또는 별도 클래스).
- 소스 무관 원칙 준수: 함수 내부에 `if source == "..."` 분기 금지.

**A3. 파이프라인 배선 (A0 Q5 결과 기반)**
- **권장 방식**: 기존 collect 경로를 건드리지 말고, `/collect/coverage`를 별도 엔드포인트로 뒀던 것과 같은 관습으로 — 저장된 아이템을 읽어 클러스터링하는 **읽기 경로**를 둔다(예: `GenerateEventsUseCase` + 전용 엔드포인트). 이렇게 하면 라이브 per-item 경로가 무손상.
- 단, A0에서 더 단순한 삽입 지점이 확인되면 그것을 우선.
- 브리핑이 Event를 소비하도록 연결(패스스루라 대부분 1-item Event이므로 기존 브리핑과 호환돼야 함).

**A4. end-to-end 실행 + 검증**
- 실제 DB 아이템으로 collect→cluster→brief 완주.
- 에러 없이 Event 리스트가 생성되고, 정확 중복이 병합됨을 확인.
- §9 테스트 통과.

---

## 9. 테스트 계획 (Test Plan)

**골든 테스트 (결정론적이므로 작성 가능)**
- **G1 정확 중복 병합**: 동일 URL 2건 입력 → Event 1개, `source_count=2`.
- **G2 URL 정규화 병합**: `?utm_source=x` 차이만 있는 2건 → 1개 Event로 병합.
- **G3 패스스루**: 서로 다른 URL N건 → Event N개, 전부 `source_count=1`.
- **G4 유일 진짜 양성은 병합 안 됨(의도된 동작)**: Anthropic "Claude Science" ↔ HN "Claude Science" — URL이 다르므로 **각각 1-item Event**. 퍼지가 아니므로 병합하지 않는 것이 정답임을 테스트로 고정.
- **G5 URL 없는 아이템**: title fallback으로 canonical_key 생성되는지.

**결정론 테스트**
- 동일 입력 2회 실행 → 동일 출력(Event 순서·id 포함). 정렬 안정성 확인.

**파이프라인 스모크**
- 실제 DB 배치로 A4 경로 완주, 예외 없음.

**회귀 가드**
- `git diff`로 스코어링 파일(§10 목록) 무수정 확인.
- 전체 테스트 스위트 그린 유지.

---

## 10. Definition of Done

- [ ] A0 노트(`docs/notes/clusterer-passthrough-a0.md`) 작성 — Q1~Q7 답변 + 리팩터 요약 1문단
- [ ] Event 모델 정의/확장 (§5 계약, A0 필드명 반영)
- [ ] `ExactDupClusterer.cluster(items) -> list[Event]` 구현
- [ ] `normalize_url` 구현 or 기존 유틸 재사용
- [ ] 기존 퍼지 로직(gate1/jaccard/org) 비활성·격리 (삭제 아님)
- [ ] 소스 무관 확인 — 클러스터 로직 내 source-name 하드코딩 분기 없음
- [ ] 파이프라인 배선 — collect→cluster→brief 완주
- [ ] 골든 테스트 G1~G5 통과
- [ ] 결정론 테스트 통과
- [ ] end-to-end 스모크 통과
- [ ] **스코어링 파일 무수정 확인** (`git diff` — `scoring_engine.py`, `SOURCE_WEIGHTS` 정의부 등)
- [ ] PROGRESS.md 갱신 (§11)
- [ ] 전체 테스트 스위트 그린

---

## 11. PROGRESS.md 갱신 항목

- **완료**: 패스스루 클러스터러 + Event 모델 배선, 파이프라인 end-to-end 검증.
- **폴리싱 이관 (근거 명시)**:
  - 퍼지 매칭(gate1/jaccard/org) — origin↔origin 0.06%, origin↔coverage 0% 실측으로 자동 병합 근거 없음. 전제조건: **coverage 5개 소스 상시 운영 후 재측정**.
  - origin↔coverage 매칭 — 동일 사유.
  - SimilarityPort/임베딩 — 퍼지 교체 지점, 미구현.
  - Event DB 영속화 — 필요성 확인 후 별도 작업.
  - `source_count`/`source_diversity` 스코어링 반영 — 다음 단계(스코어링 파일 최초 수정 지점).
- **A0 아카이브 링크**: `clusterer-origin-origin-a0-observation.md`, `clusterer-origin-coverage-a0-rerun.md`, `clusterer-passthrough-a0.md`.

---

## 부록: 폴리싱 단계 진입 조건 (기록용, 이번 구현 대상 아님)

퍼지 클러스터러를 다시 착수하는 시점의 게이트:
1. coverage 소스 5개(TechCrunch + MIT TR + Verge + MarkTechPost + Decoder) 전부 라이브
2. 수 주간 상시 수집으로 origin↔coverage 후보 쌍이 통계적으로 유의미하게 축적
3. 그 데이터로 origin↔coverage A0 재측정 → 겹침률이 임계값 튜닝 가능한 수준
4. 이때 `SimilarityPort`(TF-IDF→임베딩) 구현 + threshold 상수화 + 골든 테스트
