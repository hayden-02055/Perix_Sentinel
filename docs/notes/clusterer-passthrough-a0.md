# Clusterer Passthrough — A0 관측 노트

> SDD: `docs/SDD/Clustering/Perix_Sentinel_Passthrough_Clusterer_SDD.md`
> 날짜: 2026-07-22 · 읽기 전용 관측, 코드 무수정

이 노트는 A1~A4 구현의 근거다. **SDD 가정과 실제 코드가 다르면 실제 코드를 따르고** 아래에 불일치를 기록한다(SDD §8).

---

## Q1. `app/domain/services/clusterer.py` 현재 구조

- 진입 함수: `cluster(items: list[CollectedItem]) -> list[Event]` — **이미 SDD가 원하는 시그니처/반환 타입**(모듈 레벨 함수).
- gate1 상수: `MATCH_WINDOW_BEFORE_H=6`, `MATCH_WINDOW_AFTER_H=48` — `app/core/config.py`에 정의, `_gate1_time_window()`에서 사용.
- jaccard: `_jaccard()` + `_gate3_tiebreak()`(비-HF 우선 후 jaccard 타이브레이커).
- org overlap: `_gate2_entity()`(org 교집합 필수 + 유일후보 아니면 model intersect).
- **파이프라인 배선 여부: 미배선.** `grep` 결과 `clusterer`를 import하는 것은 `tests/test_clusterer.py` 뿐. 라이브 경로에 전혀 연결돼 있지 않은 스캐폴딩 → 격리해도 실행 파이프라인에 영향 없음.
- **소스 하드코딩 존재**: `_COVERAGE_SOURCES = {"TechCrunch","MarkTechPost"}`, `_HUGGINGFACE_SOURCE`. 이것이 SDD §I5/§A2가 격리하라는 functional-axis 분기다.

## Q2. Event/Cluster 모델 존재 여부 — **주요 불일치**

- `app/domain/models/event.py`에 `Event` + `EventMember` **이미 존재**. 단, shape가 **origin/echo 중심**(`members: list[EventMember]{role: origin|echo}`, `entities`, `echo_count`, `diversity`, `score`, `importance`, `is_briefed`) — SDD §5의 `items/primary_item/source_count/source_diversity/sources/domains/regions/first_seen/last_seen` shape가 **아님**.
- 이 Event는 **이미 영속화됨**: `SqliteEventRepository`(`events` 테이블), `EventRepositoryPort`, `main.py` lifespan에서 `init_db()`, `tests/test_event_repository.py`가 가드.
- **불일치**: SDD §3 비목표는 "Event DB 영속화 안 함(in-memory)"이라 했으나, 앞선 A1 작업에서 영속화가 이미 존재한다. SDD §5는 "있으면 확장"이라 했으나 shape가 근본적으로 다르다(origin/echo vs items/primary).
- **결정(사용자 승인 2026-07-22)**: 기존 `Event`+repo+table+test는 **퍼지 슬롯으로 그대로 보존**하고, ExactDup용 **신규 `PassthroughEvent`**(§5 shape, in-memory)를 별도 모델로 만든다. → §3(in-memory), §6(퍼지 격리), §8(실제 코드 우선) 모두 충족.

## Q3. `CollectedItem` 실제 필드 — **부분 불일치(domain/region 위치)**

- URL 필드명: **`url`** ✅
- timestamp: **`published_at`** ✅
- `source` ✅, `tags: list[str]` ✅, `metadata: dict` ✅
- **`domain`/`region`은 top-level 필드가 아님** — `metadata` dict 안에 있음(예: `metadata={"function","domain","region","feed"}`, 컬렉터마다 채움).
  - → §5/I4 `source_diversity = distinct domain`은 `item.metadata.get("domain")`로 읽는다. `regions`도 `item.metadata.get("region")`.
  - 일부 소스(arXiv/HN 등)는 `domain`/`region` 미채움 → `None` 제외하고 distinct 집계.

## Q4. `entity_extractor.py`

- 콤마 버그 수정 반영됨(`_SEP_RE = re.compile(r"[-_/',]")`, 콤마 포함).
- `extract_entities(title) -> dict`, `tokenize(text) -> list[str]`. 퍼지 슬롯에서 계속 사용하므로 무수정 유지.

## Q5. 브리핑/파이프라인 배선 지점

- 브리핑은 **아이템 단위**: `CollectTrendsUseCase.execute()`가 collect 시점에 per-item `apply_score` → `BRIEFING_THRESHOLD` 이상이면 `DiscordPublisher.publish` → `mark_briefed_by_hash`.
- 저장된 아이템을 **다시 읽어 클러스터링하는 경로는 없음**. repository 읽기 메서드는 `get_by_id`, `get_unsummarized`(summary='' 한정)만.
- **가장 덜 침습적인 삽입 지점**: 라이브 per-item 경로를 건드리지 말고, 저장 아이템을 읽어 클러스터링하는 **읽기 경로**(신규 `GenerateEventsUseCase` + 읽기 전용 엔드포인트)를 추가(SDD §8 A3 권장). 이를 위해 `ItemRepositoryPort`에 읽기 메서드 1개(`get_recent`) 추가 필요.

## Q6. 포트/유틸 존재 확인

- `ClustererPort` 없음 → 신규(`app/domain/ports/clusterer_port.py`).
- **URL 정규화 유틸 없음**(`deepmind_html_collector`만 `urlparse`로 도메인 allowlist 체크). → `normalize_url` 신규(`app/core/url_utils.py`).

## Q7. 기존 테스트

- `tests/test_clusterer.py`(퍼지 7종, `from ... import cluster`), `test_entity_extractor.py`, `test_event_repository.py`.
- 퍼지 격리 시 `test_clusterer.py`의 import만 기계적으로 `FuzzyClusterer`로 갱신(로직/기대값 불변).

---

## 요약: 무엇을 비활성/격리하고 무엇을 신규 생성하는가

기존 `clusterer.py`의 퍼지 3게이트(`_gate1_time_window`/`_gate2_entity`/`_gate3_tiebreak` + 소스 하드코딩)와 origin/echo `Event`+`events` 테이블은 **삭제 없이 퍼지 폴리싱 슬롯으로 보존**한다(퍼지 로직은 `FuzzyClusterer` 클래스로 감싸 격리, 반환은 기존 `Event` 유지). **신규 생성**: `PassthroughEvent`(§5 shape, in-memory) · `ExactDupClusterer.cluster(items) -> list[PassthroughEvent]`(canonical URL/title 정확 중복만, 소스 무관) · `normalize_url`/`canonical_key`(신규 유틸) · `ClustererPort` · 읽기 경로(`ItemRepositoryPort.get_recent` + `GenerateEventsUseCase` + 읽기 전용 엔드포인트). 스코어링 파일과 라이브 collect 경로는 무수정.
