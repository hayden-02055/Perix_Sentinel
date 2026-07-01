# Perix Sentinel — 컬렉터 정리본

> AI 생태계 신호 수집 컬렉터 전체 현황.
> 최종 갱신: 2026-07-01

---

## 0. 태그 체계

모든 컬렉터는 3개 축으로 태깅한다. 나중에 "하드웨어만" / "중국 랩만" 같은 필터를 공짜로 얻기 위함.

| 축 | 값 | 의미 |
|---|---|---|
| **function** | `origin` / `coverage` | 사건을 **생성**하는가, 사건을 **커버(교차보도)**하는가 |
| **domain** | `core-lab` / `hardware` / `academia` / `ecosystem` / `community` | 소스의 성격 |
| **region** | `us` / `eu` / `cn` / `ca` / `global` | 소속 지역 |

### domain 정의

- `core-lab` — 프론티어 모델 연구소 (OpenAI·Anthropic·DeepSeek 등)
- `hardware` — 칩·인프라 (NVIDIA·AMD·TPU)
- `academia` — 논문·대학 랩 (arXiv)
- `ecosystem` — 모델/코드/툴 배포 허브 (HuggingFace·GitHub)
- `community` — 토론·큐레이션 (Hacker News·Reddit)

> **function 원칙**: origin만 "사건(event)"을 생성한다. coverage는 항목을 만들지 않고, origin 사건에 매칭시켜 "몇 곳이 다뤘나"로 중요도를 가산한다. (스코어링은 Tier2 통합 후 설계)

---

## 1. 현재 컬렉터 (11개) — Tier 1 완료

| # | 컬렉터 | 소스 | domain | region | function | 수집 방식 | 상태 |
|---|---|---|---|---|---|---|---|
| 1 | AnthropicHtmlCollector | anthropic.com | `core-lab` | `us` | origin | HTML | ✅ live |
| 2 | OpenAIRssCollector | openai.com | `core-lab` | `us` | origin | RSS | ✅ live |
| 3 | MistralHtmlCollector | mistral.ai | `core-lab` | `eu` | origin | HTML | ✅ live |
| 4 | MetaHtmlCollector | ai.meta.com/blog | `core-lab` | `us` | origin | HTML | ✅ live |
| 5 | DeepmindHtmlCollector | deepmind.google | `core-lab` | `us` | origin | HTML | ✅ live |
| 6 | GoogleResearchRssCollector | research.google | `core-lab` | `us` | origin | RSS | ✅ live |
| 7 | GitHubTrendingCollector | github.com (Trending) | `ecosystem` | `global` | origin | HTML | ✅ live |
| 8 | HuggingFaceApiCollector | huggingface.co | `ecosystem` | 파생¹ | origin | API | ✅ live |
| 9 | ArxivApiCollector | arxiv.org | `academia` | `global` | origin | API | ✅ live |
| 10 | HackerNewsApiCollector | news.ycombinator.com | `community` | `global` | origin | Firebase API | ✅ live |
| 11 | NvidiaRssCollector | developer.nvidia.com | `hardware` | `us` | origin | RSS | ✅ live |

> ¹ HuggingFace region은 고정값이 아니라 **조직 핸들·모델명에서 파생**. `_ORG_REGION` 조직 매핑 → `_FAMILY_REGION` substring 폴백 → `global`. 중국 랩(`zai-org`, `Qwen` 등) → `cn`, 미국 랩(`meta-llama`) → `us`, EU(`mistralai`) → `eu`, 미식별 → `global`.

**현황 요약**
- 11개 소스 라이브, DB 2,000+ rows, 파이프라인 e2e 동작
- 도메인 커버리지: `core-lab` 5개(Anthropic·OpenAI·Mistral·Meta·DeepMind) + `core-lab` 1개(Google Research) + `hardware` 1개(NVIDIA) + `ecosystem` 2개 + `academia` 1개 + `community` 1개
- 중국 랩 커버: HF region 파생으로 흡수 (§3 참조)
- HTML 파싱(1·3·4·5·7)은 구조 변경 시 취약 → 유지보수 부채

> **비고 — function/domain/region 태그 현황**: NVIDIA·Google Research·HuggingFace는 metadata에 3개 태그 부착 완료. 나머지 컬렉터(OpenAI·Anthropic·Mistral·Meta·DeepMind·GitHub·arXiv·HN)는 region/function/domain 백필 미완료 → 다음 작업(§4) 참조.

---

## 2. 신규 제안 컬렉터

### 2-1. 후순위 (HTML/피드없음 — 리스크 있어 나중에)

| 제안 컬렉터 | 소스 | domain | region | function | 수집 방식 | 난이도 |
|---|---|---|---|---|---|---|
| AmdCollector | amd.com | `hardware` | `us` | origin | HTML 추정 | 🟡 중간 |
| CohereCollector | cohere.com | `core-lab` | `ca` | origin | HTML | 🟡 중간 |
| xAICollector | x.ai | `core-lab` | `us` | origin | 피드 없음 (X 중심) | 🔴 어려움 |

> NVIDIA·Google Research는 모두 완료돼 §1로 이동. 잔여 후보는 HTML/피드 없음 리스크가 있는 3건만 남음.

---

## 3. 중국 프론티어 랩 — HuggingFace로 흡수 ✅

DeepSeek · Qwen(Alibaba) · GLM(Zhipu) · Kimi(Moonshot) 는 **자체 공개 RSS가 없다.**
개별 스크래퍼로 가면 죽은 HTML 컬렉터 5개와 같은 벽에 부딪힌다.

**방법: 기존 HuggingFace 컬렉터(#8)로 흡수 + region 파생 태깅 구현 완료.**
- HF 컬렉터가 잡은 항목에 조직명 매핑(`_ORG_REGION`)·모델명 substring(`_FAMILY_REGION`)으로 `region=cn` 태그 부착
- 재업로드(예: `bartowski/Qwen2.5-GGUF`) → author가 커뮤니티 계정이어도 model_id substring으로 구제

| 랩 | 모델군 | 처리 방침 | 파생 결과 |
|---|---|---|---|
| DeepSeek | DeepSeek V4 | HF 흡수 | `domain=ecosystem` / `region=cn` |
| Alibaba | Qwen | HF 흡수 | `domain=ecosystem` / `region=cn` |
| Zhipu (Z.ai) | GLM | HF 흡수 | `domain=ecosystem` / `region=cn` |
| Moonshot | Kimi | HF 흡수 | `domain=ecosystem` / `region=cn` |

> **미포함 중국 조직**: `baidu`가 실가동(A0)에서 트렌딩으로 등장. 현재 `_ORG_REGION` 목록 외라 `global`로 태깅됨. 다음 `_ORG_REGION` 확장 시 추가 필요.

---

## 4. 우선순위 & 다음 작업

완료된 항목:
1. ~~태그 필드 3개 확정~~ — `function` / `domain` / `region` → HF·NVIDIA·GR에 부착 완료 ✅
2. ~~NvidiaRssCollector~~ — `hardware` 도메인 첫 소스, RSS 기반 ✅
3. ~~HF 컬렉터 `region=cn` 태깅~~ — 조직명+모델명 파생으로 중국 랩 커버 완료 ✅
4. ~~GoogleResearchRssCollector~~ — `core-lab` 보강, 비-AI 25% → 카테고리 화이트리스트 필터 적용 ✅

남은 작업:
5. **타 컬렉터 function/domain/region 백필** — OpenAI·Anthropic·Mistral·Meta·DeepMind·GitHub·arXiv·HN. 전부 상수라 간단하나 범위 분리됨.
6. **(후순위)** AMD·xAI·Cohere — HTML/피드없음 리스크가 있어 검증 후 진행
7. **(Tier2)** coverage 소스 설계 — 뉴스레터·미디어 추가 전 function=coverage 파이프라인 설계 필요

---

## 5. 참고: 스코어보드(coverage) 소스 — 아직 미착수

> function=`coverage`. origin 사건의 중요도를 측정하는 교차보도 풀. Tier2 설계 시 확정 예정.

- 뉴스레터: TLDR · The Batch · Rundown 등
- 미디어: TechCrunch · Wired · MIT Tech Review 등
- 컬럼/오피니언: (coverage로 분류 — 새 사건이 아니라 사건 분석)

> 미해결 질문: coverage 풀을 뉴스레터로 좁힐지, 미디어까지 넓힐지 → Tier2 설계의 핵심 병목.
