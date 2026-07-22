# Origin-Origin 중복 A0 관측 (신규 SDD 착수 전)

작성일: 2026-07-22

## 배경

기존 `clusterer-event-a0-observation.md`(2026-07-21)는 **origin vs coverage**(TechCrunch/
MarkTechPost) 매칭만 관측했다. 이번 요청은 범위가 다르다: **origin 소스끼리**(OpenAI,
Anthropic, DeepMind, Google Research, NVIDIA, Meta, Mistral, HuggingFace, arXiv, GitHub
Trending, Hacker News) 같은 사건을 중복 보도하는 케이스가 실제로 얼마나 있는지 측정한다.
PROGRESS.md의 미해결 항목("DeepMind 의미중복 — deepmind.google과 research.google는 별개
소스로 유지, 의미 중복 병합은 Clusterer로 이월")이 이 관측의 직접 동기다.

방법: `app/domain/services/entity_extractor.py`(조직 사전)와 `clusterer.py`의 Jaccard 구현을
그대로 재사용해 clusterer 로직과 동일 기준으로 비교 가능하게 했다. 스크립트는 읽기 전용,
`perix_sentinel.db`에 쓰기 없음.

## 결과 요약

- **origin 아이템 총 1,585건** (coverage 2소스 제외), 11개 소스
- 조직명이 겹치는 **cross-source pair 705개** — 관여 아이템 136건/1,585건 (**8.6%**)
  - 단, 이 705개는 시간 제약이 없다. 대부분 Δt가 수백~수천 시간(즉 "같은 조직을 여러 번
    언급"이지 "같은 사건"이 아니다).
- clusterer가 이미 쓰는 현실적 시간창(±48h)으로 좁히면 **35쌍**만 남는다.
- 이 35쌍을 전수 검토(사람 육안)한 결과 **실제 같은 사건은 1쌍뿐**.
  - **origin-origin 실제 중복률 ≈ 1/35 (2.9%)** (48h창 후보 기준) / **1/1,585 (0.06%)**
    (전체 아이템 기준)

**결론: 실측 중복률이 사실상 0에 가깝다.** 임계값을 정교하게 설계할 근거가 될 만큼의
표본이 없다 — 이전 origin-vs-coverage A0(2026-07-21)와 같은 구조적 결론이 origin-origin
에서도 재현됐다.

## 대표 케이스 5개

| # | 소스 A | 소스 B | Δt | jaccard | org | 실제 동일 사건? |
|---|---|---|---|---|---|---|
| 1 | Anthropic: "Claude Science, an AI workbench for scientists, is now available" (06-30 00:00) | Hacker News: "Claude Science" (06-30 17:07) | **17.1h** | **0.09** | anthropic | **예 — 유일한 실제 중복.** HN이 Anthropic 발표를 그대로 토론 스레드화. |
| 2 | Anthropic: "Claude Fable 5 and Claude Mythos 5" (06-09) | Hacker News: "Department of Commerce has lifted export controls on Claude Fable 5 and Mythos 5" (06-30) | 527.9h | **0.38 (전체 최고)** | anthropic | 아니오 — 3주 뒤 별개 수출규제 뉴스. 모델명 반복 언급일 뿐. |
| 3 | Anthropic: "Introducing Claude Sonnet 5" (06-30) | Hacker News: "Claude Fable 5 available globally tomorrow" (07-01) | 28.4h | 0.25 | anthropic | 아니오 — Sonnet 5 발표와 Fable 5 롤아웃은 다른 제품 이벤트. 48h창 안에 들어와 "근접 오탐" 사례. |
| 4 | Anthropic: "Introducing Claude Sonnet 5" (06-30) | HuggingFace: "empero-ai/Qwythos-9B-Claude-Mythos-5-1M" (06-28) | 31.4h | 0.20 | anthropic | 아니오 — 공식 발표 vs 제3자 커뮤니티 파인튜닝. PROGRESS.md의 기존 "HF title 구조 문제" 미결 사항과 동일 패턴 재확인. |
| 5 | OpenAI: "How NVIDIA engineers and researchers build with Codex" (05-12) | NVIDIA: "How to Automate AI Model Documentation with the NVIDIA MCG Toolkit" (05-29) | 1528h | 0.24 | nvidia | 아니오 — OpenAI 글이 NVIDIA를 파트너로 언급했을 뿐, 조직명만 겹치는 전형적 롱테일 오탐. |

## 임계값 설계에 대한 시사점 (SDD 작성 전 확인 필요)

1. **Jaccard를 1차 게이트로 쓰면 안 된다.** 유일한 진짜 양성(#1)이 jaccard=0.09로, 전체
   후보 중 최저권이다. 반대로 최고 jaccard(0.38, #2)는 가짜다. Jaccard는 기존
   `clusterer.py` 설계대로 **타이브레이커 이하 역할**만 맡아야 한다는 결론이 origin-origin
   에서도 그대로 재확인됨.
2. **토크나이저 punctuation 버그 발견**: `entity_extractor.tokenize()`가 `,`를 구분자로 처리
   하지 않아 `"Science,"` 같은 트레일링 콤마 토큰이 `"Science"`와 매칭되지 않는다. #1의
   jaccard가 실제보다 낮게 나온 원인 중 하나(콤마 제거 시 0.09 → 0.20). 별도 이슈로 기록.
3. **표본이 근본적으로 부족하다.** 48h창 내 진짜 중복이 1건뿐이라 "몇 시간 창이 적절한가",
   "org+model 교집합 요구 수준" 같은 파라미터를 이 데이터만으로 확정할 수 없다. 임계값을
   지금 SDD에 박으면 사실상 감으로 잡는 것과 같다.
4. **원인은 origin 커버리지 자체의 성격**: 11개 origin 소스 대부분이 서로 다른 조직의
   공식 채널이라 애초에 같은 사건을 두 번 보도할 일이 드물다(자사 발표는 자사만 함). 예외는
   HN처럼 "타 조직 발표를 토론하는" 소스뿐이며 관측된 유일한 진짜 사례(#1)도 이 패턴이다.

## 재실행 (콤마 토크나이저 버그 수정 후, 2026-07-22)

`entity_extractor.tokenize()`의 `_SEP_RE`에 `,` 추가 후 동일 스크립트 재실행(읽기 전용,
DB 무변경).

- **후보 수 불변**: cross-source org-overlap 705쌍, 48h창 내 35쌍 — 콤마는 org 별칭 토큰
  (단일 단어, 콤마 안 붙음) 추출에 영향이 없어 후보 집합 자체는 그대로.
- 유일한 진짜 양성 쌍의 jaccard가 **0.09 → 0.20**으로 정정됨(콤마 제거로 "science,"↔"science"
  매칭 성립). 35쌍 전체를 다시 검토해도 진짜 동일 사건은 여전히 그 1건뿐.
- **결론: 0.06%(1,585건 중 1건)는 측정 아티팩트가 아니라 실측치로 확정.**
- 버그 수정 후에도 **최고 jaccard(0.27)는 여전히 가짜 쌍**(Anthropic "Claude Science, an AI
  workbench..." ↔ HN "Claude Desktop is now available on Linux") — "jaccard는 1차 게이트가
  될 수 없다"는 결론도 아티팩트가 아니라 그대로 유지된다.

## 권장

- **origin-origin 중복 병합 SDD는 지금 쓰지 않는 것을 권장.** 표본 1건으로 임계값을 정하면
  검증 불가능한 추측이 된다.
- 대안: (a) 2주 더 관측 후 재평가(기존 A2b 재평가 조건과 동일 주기로 묶기), 또는
  (b) 임계값 설계 없이 "org overlap + ≤48h + 사람 확인 큐" 같은 저위험 휴리스틱만 우선
  넣고 자동 병합은 보류.
- DeepMind/Google Research 의미중복(PROGRESS.md 기존 미결)은 이번 관측에서 org 사전에
  둘 다 `"google"`로 묶여 있어(§`_ORG_ALIASES`) cross-source 후보에는 잡히지만, 이번 35쌍
  안에는 실제 겹치는 사건이 없었다 — 별도로 계속 관찰 필요.
