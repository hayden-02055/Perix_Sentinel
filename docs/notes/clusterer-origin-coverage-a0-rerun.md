# Origin ↔ TechCrunch 재측정 (콤마 토크나이저 버그 수정판, 2026-07-22)

## 배경

`clusterer-event-a0-observation.md`(07-21)가 origin↔coverage(TechCrunch+MarkTechPost 합산)
매칭을 이미 관측했으나 콤마 버그 수정 전이었고, MarkTechPost와 합산 집계였다. 이번엔
**TechCrunch만 단독**, 프로덕션 게이트(`clusterer.py`의 실제 `_gate1_time_window`/`_jaccard`,
`entity_extractor`를 그대로 import)로 재측정했다. 읽기 전용, DB 무변경.

## 결과

- TechCrunch 20건 / origin 1,585건
- **프로덕션 gate1(-6h/+48h) + org 교집합 통과 pair 수: 0쌍 (매칭률 0/20 = 0%)**
  — 07-21 라이브 재확인과 동일 결론 재현, 콤마 버그 수정 후에도 변화 없음.
- 시간창을 풀고 org 교집합만 볼 경우: **230쌍**, 관여 TechCrunch row **2/20 (10%)**
  - 그러나 229/230쌍이 Δt 168h(1주) 초과, 최단 쌍도 115.6h(약 5일)
  - 관여 row 2개 중 하나("OpenAI is scared of open-weight models. Should the US be?")가
    "openai" 조직명만으로 OpenAI 아카이브 전체(1,059건)와 닥치는 대로 걸려 229쌍을 혼자
    만들어냄 — 실제 내용 연관 없음(오피니언 칼럼 vs 무관한 파트너십/사내소식 포스트).

**Δt 분포(org 교집합 230쌍 기준)**: `<0h` 0 / `0-6h` 0 / `6-48h` 0 / `48-168h` **1** / `168h+` **229**

## 대표 케이스 5개 (전부 오탐 — 진짜 동일 사건 0건)

| # | TechCrunch | origin | Δt | jaccard | 실제 동일 사건? |
|---|---|---|---|---|---|
| 1 | "OpenAI is scared of open-weight models. Should the US be?" (07-20) | OpenAI: "The next phase of the Microsoft OpenAI partnership" (04-27) | +2029.6h | 0.20 | 아니오 — 오피니언 칼럼 vs 파트너십 발표, 무관 |
| 2 | 상동 | OpenAI: "PVH reimagines the future of fashion with OpenAI" (01-27) | +4189.6h | 0.19 | 아니오 |
| 3 | "Google is working on a new AI chip designed to make Gemini more efficient" (07-20) | DeepMind: "Gemini for Science: AI experiments and tools for a new era of discovery" (05-01) | +1941.4h | 0.18 | 아니오 — 칩 뉴스 vs 과학 도구 소개, 무관 |
| 4 | "OpenAI is scared of open-weight models..." | OpenAI: "OpenAI and PwC collaborate to reimagine the office of the CFO" (05-04) | +1846.6h | 0.17 | 아니오 |
| 5 | "OpenAI is scared of open-weight models..." | OpenAI: "How Cars24 scales conversations and builds faster with OpenAI" (07-16) | **+115.6h (가장 근접)** | 0.11 | 아니오 — 가장 가까운 쌍조차 무관 |

## 결론

**매칭 쌍 수 = 0, 겹침률 = 0%.** TechCrunch 단독으로 봐도 origin과의 실제 동일사건 중복은
관측되지 않았다. `entity_extractor`의 org 사전이 "OpenAI"처럼 흔한 조직명을 넓게 잡을수록
시간창 없이는 노이즈(229쌍)만 커진다는 것도 재확인됨 — 프로덕션 gate1의 시간창 제약이
왜 필요한지에 대한 근거가 하나 더 쌓였다.

기존 결론(`clusterer-event-a0-observation.md`) 변경 없음: **origin↔coverage 자동 병합은
여전히 실증 데이터가 없다.** 새 정보는 "TechCrunch만 떼어놔도 동일하다"는 재확인뿐이다.
