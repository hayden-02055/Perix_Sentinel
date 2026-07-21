# Perix Sentinel — Test Infra Fix & Mistral Revival Wrap-up SDD

> Software Design Document · v0.1 (Light)
> 트리거: Mistral 부활 리뷰(`mistral-collector-revival-review.md`) — 골든 테스트가 `5 skipped`로 실제 검증을 못 하고 있음.
> 전제: **이 SDD는 "skip이 Mistral 한정"일 때만 유효하다.** (§G0 게이트에서 확정)

---

## 0. 한 줄 요약

D5에서 추가한 Mistral 골든 테스트가 `pytest-asyncio` 문제로 **실행되지 않고 skip**되어 사실상 보호 효과가 0이다. 이 SDD는 (1) 테스트 인프라를 고쳐 그 테스트를 **실제로 실행**시키고, (2) 직전에 남겨둔 **부활 DoD(`/collect` 실가동)**를 닫으며, (3) 리뷰의 자잘한 지적을 **기존 공통 부채에 합류**시킨다. 무겁지 않게.

---

## G0. 선행 게이트 — skip 범위 확정 (필수)

작업 시작 전 단 한 번:

```bash
pytest -v
```

판정:

| 관측 | 의미 | 행동 |
|---|---|---|
| `skipped`가 **Mistral 5개뿐** | D5에서만 노출된 국소 문제 | **이 SDD 계속 진행** |
| `skipped`가 **Anthropic 골든/기타 async까지** | 안전망이 여러 페이즈에서 무효였음 | **이 SDD 중단.** 합의대로 "안전망 소급 복구"는 **Tier1 보강 후 전반 정리**로 미룸 |

> 정황 가설: P0 "14 passed" · P1 "37 passed" 보고에 skip이 안 섞였다면 async는 그 시점엔 동작 → **Mistral-only 가능성 높음.** 그래도 추측으로 넘기지 말고 G0로 사실 확정.

---

## 1. 목표 (Goals) — Mistral-only 전제

1. Mistral 골든 테스트가 **`5 passed`로 실제 실행** (skip 0)
2. 부활 DoD 마무리: **`POST /collect` 1회로 6개 소스가 실제 DB row 생성**
3. 리뷰 지적(날짜 fallback·urljoin)을 **올바른 우선순위로 분류** (지금 vs 부채)

## 2. 비목표 (Non-Goals)

- 안전망 소급 복구 (G0에서 spread로 나오면 → 별도, Tier1 후)
- Tier1 보강(arXiv·HN), 스코어링 재보정, LLM 요약
- P2 BaseHtmlCollector

---

## 3. 작업 항목

### T1. pytest-asyncio 복구 — P1 (최우선)
**문제**: `@pytest.mark.asyncio` 미인식 → async 테스트 skip. 골든 테스트가 동작을 전혀 보호하지 못함.
**처방**:
- `pytest-asyncio` 설치 확인 (`requirements.txt`엔 이미 `pytest-asyncio==0.24.0` 명시됨 → 실행 환경/venv 불일치 의심)
- `pytest.ini`에 `asyncio_mode = auto` 확인/추가 → 명시적 마커 없이도 async 자동 수집
- `asyncio_default_fixture_loop_scope` 경고 정리
**DoD**: `pytest tests/test_mistral_collector_golden.py -q` → `5 passed`, skip 0.

### T2. 골든 fixture 실검증 확인 — P1
**문제**: T1 전까진 75건 fixture가 단 한 번도 실제 비교된 적 없음.
**처방**: T1 후 골든 JSON 75건이 파싱 결과와 실제로 일치하는지 그린 확인. 불일치 시 fixture/파서 중 어디가 어긋났는지 분리.
**DoD**: 75건 비교가 실제로 수행되고 통과.

### T3. `/collect` 실가동 — 부활 DoD 마감 — P1
**문제**: D0에서 4개 컬렉터가 "단독 실행 정상"이었으나, **파이프라인 실가동(F1 원인) 확인은 미완**. "단독 정상 ≠ DB 적재".
**처방**: `POST /collect` 1회 실행 → 소스별 row 수 집계.
**DoD**: OpenAI·Anthropic·DeepMind·Meta·Mistral·HuggingFace·GitHub 중 **6개 이상**이 실제로 row 생성. 단독은 되는데 여기서 0이면 → wiring(레지스트리/실행 루프)이 진짜 F1 원인 → 그 지점 수정.

### T4. 리뷰 지적 분류 — P2~부채
리뷰의 3개 지적을 우선순위로 정리:

| 리뷰 항목 | 분류 | 행동 |
|---|---|---|
| ① 테스트 skip | **지금 (T1)** | 위에서 처리 |
| ② urljoin 미사용 | 견고성, 소형 | T1~T3 그린 후 **tidy 커밋 1개**로 처리 (선택) |
| ③ 날짜 silent fallback | **공통 부채** | 개별 수정 ❌ — P1 회고·D0에서 이미 나온 동일 패턴. **프로젝트 공통 "fallback 가시화" 부채로 통합**, 나중에 일괄 |

> ③을 Mistral에서만 또 고치면 같은 코드를 소스마다 N번 손대게 됨. **공통 부채로 묶어 한 번에**가 원칙(P1 회고 때 합의).

---

## 4. 작업 순서 & 브랜치

브랜치: `fix/test-infra-mistral-wrapup`

```
G0  pytest -v → skip 범위 확정 (Mistral-only면 계속)
T1  pytest-asyncio 복구 → 5 passed
T2  골든 75건 실검증 그린
T3  POST /collect → 6소스 적재 확인 (부활 DoD 마감)
T4  (선택) urljoin tidy / ③은 부채 등록만
```

각 단계 그린 후 다음. T3에서 부활이 비로소 "완료" 선언 가능.

---

## 5. 완료 정의 (DoD)

- [ ] G0: skip 범위 = Mistral 한정 확정 (아니면 이 SDD 중단)
- [ ] `pytest` 전체에서 의도치 않은 `skipped` 0
- [ ] Mistral 골든 `5 passed`, 75건 실비교 통과
- [ ] `POST /collect` → 6개 이상 소스 DB 적재 (부활 DoD 마감)
- [ ] silent date fallback(③)은 **공통 부채로 PROGRESS에 등록** (이번엔 구현 안 함)

---

## 6. 리스크

- **G0가 spread로 나올 위험** → 그 즉시 중단·미루기. 이 SDD를 억지로 진행하지 않음. (자기방어 게이트)
- **T3에서 6소스 미달** → 단독 정상인데 미적재면 wiring 결함. 이 경우 **컬렉터별 실패 격리(P1 회고의 미구현 항목)**가 없어서 한 곳 예외가 전체를 죽이는지부터 확인.
- **fixture 75건 과대** → 회귀엔 과한 크기. 트림은 부채 후보(지금 안 함).

---

## 7. 다음 연결

이 SDD 종료 → **Tier1 보강**(arXiv·HN) → 소스 충분해지면 **스코어링 재보정(17%→5%)**.
G0에서 spread가 확인됐다면 → 안전망 소급 복구를 **Tier1 보강 후 전반 정리 라운드**에서 통합 처리.
