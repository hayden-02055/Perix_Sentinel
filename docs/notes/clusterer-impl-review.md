# Clusterer 구현 리뷰

작성일: 2026-07-21

## 요약

이번 변경은 A1 Event 저장소 리뷰 후속 조치를 반영하고, A2a 범위의 `entity_extractor.py`와
`clusterer.py` 순수 로직을 추가한 작업이다. `SqliteEventRepository.upsert()`는 briefed 상태를
단조 보존하도록 수정됐고, 빈 `event_id`는 거부된다. Clusterer는 origin 항목을 Event로 만들고
TechCrunch/MarkTechPost coverage를 시간창, 개체 게이트, 제목 Jaccard 타이브레이커로 최대 1개
Event에 붙인다.

## 주요 리뷰 의견

### 1. unique-candidate 게이트가 "같은 조직 후보"가 아니라 "전체 시간창 후보" 기준임

- 위치: `app/domain/services/clusterer.py:127-135`

현재 `candidate_count = len(candidate_idxs)`는 시간창을 통과한 모든 origin 후보 수다. 이후
`_gate2_entity(..., candidate_count)`에서 `candidate_count == 1`일 때만 모델 교집합 없이
조직 교집합만으로 통과시킨다.

문제는 SDD의 의도가 "시간창 안에 **해당 조직** origin이 하나뿐이면 모델명 없이도 인정"이라는
점이다. 지금 구현은 OpenAI coverage 하나와 시간창 안의 무관한 NVIDIA origin 하나가 함께 있을
때, OpenAI 후보가 해당 조직 기준으로는 유일해도 `candidate_count == 2`가 되어 탈락한다.
이건 false negative로 이어진다.

권장:

- gate2에 넘기는 count를 전체 시간창 후보 수가 아니라 `origin_entities[idx]["org"]`와
  `coverage_entities["org"]`가 겹치는 후보 수로 바꾼다.
- 회귀 테스트를 추가한다: 같은 시간창에 OpenAI origin 1개 + 무관한 NVIDIA origin 1개가 있고,
  OpenAI coverage가 모델명을 포함하지 않아도 OpenAI Event에 붙어야 한다.

### 2. 너무 넓은 alias/model family가 오탐을 만들 수 있음

- 위치: `app/domain/services/entity_extractor.py:26-34`

화이트리스트 전환은 A0의 날짜류 오탐을 제거하는 데 효과적이다. 다만 `"command"`를 Cohere
조직 alias와 모델 family로 동시에 둔 것은 폭이 넓다. 일반 문장에 `"command"`가 들어가면
`org={"cohere"}`, `model={("command", "")}`가 생길 수 있다. `"phi"`, `"meta"`도 문맥에 따라
비모델/비조직 단어로 쓰일 수 있다.

권장:

- 특히 `"command"`는 `cohere`가 같이 등장하거나 `Command R/R+` 같은 더 구체적인 패턴일 때만
인정하는 쪽을 검토한다.
- 실DB 100건 오탐 0건은 좋은 신호지만, 이 alias들은 장기 운영 샘플에서 별도 카운트로 관찰하는
편이 안전하다.
- 테스트에 `"command line tools"` 같은 비모델 문장을 추가해 현재 의도 여부를 명시한다.

### 3. `EventMember.item_id=url_hash`는 A3에서 바로 결정을 요구함

- 위치: `app/domain/services/clusterer.py:28-36`
- 관련 미결: `PROGRESS.md`의 `item_id` 결정 사항

Clusterer가 순수 함수라 DB 정수 id를 알 수 없는 점은 타당하다. 그래서 현재는
`EventMember.item_id`에 `CollectedItem.url_hash`를 넣는다. 하지만 A3 설계의
`ItemRepositoryPort.mark_briefed(item_id: int)`와는 타입/의미가 맞지 않는다.

권장:

- A3 시작 전에 `get_unbriefed_since()` 반환 타입을 `list[tuple[int, CollectedItem]]`로 할지,
  `CollectedItem`에 repository id를 싣는 별도 DTO를 둘지 먼저 확정한다.
- 그 결정 전까지는 이 값이 "DB id가 아니라 url_hash"라는 사실을 테스트명이나 주석에 계속
명시하는 것이 좋다.

### 4. 신규 핵심 파일들이 untracked 상태라 `git diff`만으로 리뷰가 누락될 수 있음

- 확인 명령: `git status --short`

현재 `git diff`에는 추적 중인 5개 파일만 보인다. 실제 구현 핵심인 아래 파일들은 아직
untracked 상태다.

- `app/domain/services/clusterer.py`
- `app/domain/services/entity_extractor.py`
- `docs/SDD/Clustering/Perix_Sentinel_Clusterer_Impl_SDD_A2a_A3.md`
- `tests/test_clusterer.py`
- `tests/test_entity_extractor.py`

커밋 전에 반드시 stage해야 한다.

## 잘된 점

- A1 리뷰에서 지적한 `is_briefed` 되돌림 문제와 빈 `event_id` 문제를 저장소와 회귀 테스트로
  둘 다 막았다.
- Clusterer를 순수 함수로 유지해 DB, publisher, scheduler와 분리한 점은 A2a 범위에 맞다.
- A0 음성 케이스, 시간창 경계, 타이브레이커, HF 예외, 단일 귀속, event id 멱등성을 테스트로
  고정했다.
- MarkTechPost summary boilerplate 문제를 title-only 매칭으로 우회한 설계와 구현이 일치한다.

## 검증 결과

- `.venv/bin/pytest tests/test_event_repository.py tests/test_entity_extractor.py tests/test_clusterer.py`
  - 결과: `16 passed`
- `.venv/bin/pytest`
  - 결과: `78 passed, 72 warnings`

테스트는 통과한다. 다만 1번 unique-candidate 기준 문제는 현재 테스트가 커버하지 못하는
false negative라 A3 전에 고치는 편이 좋다.
