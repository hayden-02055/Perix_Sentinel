# Perix Sentinel — 컬렉터 정리본

> AI 생태계 신호 수집 컬렉터 전체 현황.
> 최종 갱신: 2026-07-04 (TechCrunch coverage 컬렉터 추가 — store-only 배선)

---

## 0. 태그 체계

모든 컬렉터는 3개 축으로 태깅한다. 나중에 "하드웨어만" / "중국 랩만" 같은 필터를 공짜로 얻기 위함.

| 축 | 값 | 의미 |
|---|---|---|
| **function** | `origin` / `coverage` | 사건을 **생성**하는가, 사건을 **커버(교차보도)**하는가 |
| **domain** | `core-lab` / `hardware` / `academia` / `ecosystem` / `community` / `media` | 소스의 성격 |
| **region** | `us` / `eu` / `cn` / `ca` / `global` | 소속 지역 |

### domain 정의

- `core-lab` — 프론티어 모델 연구소 (OpenAI·Anthropic·DeepSeek 등)
- `hardware` — 칩·인프라 (NVIDIA·AMD·TPU)
- `academia` — 논문·대학 랩 (arXiv)
- `ecosystem` — 모델/코드/툴 배포 허브 (HuggingFace·GitHub)
- `community` — 토론·큐레이션 (Hacker News·Reddit)
- `media` — 기술 미디어 (TechCrunch·MIT TR·The Verge 등) — `function=coverage` 전용

> **function 원칙**: origin만 "사건(event)"을 생성한다. coverage는 항목을 만들지 않고, origin 사건에 매칭시켜 "몇 곳이 다뤘나"로 중요도를 가산한다. (스코어링은 Tier2 통합 후 설계)

---

## 1. 현재 컬렉터 (12개) — Tier 1 완료 + Tier 2 첫 coverage

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
| 12 | TechCrunchRssCollector | techcrunch.com (AI) | `media` | `us` | coverage | RSS | ✅ live (store-only²) |

> ¹ HuggingFace region은 고정값이 아니라 **조직 핸들·모델명에서 파생**. `_ORG_REGION` 조직 매핑 → `_FAMILY_REGION` substring 폴백 → `global`. 중국 랩(`zai-org`, `Qwen` 등) → `cn`, 미국 랩(`meta-llama`) → `us`, EU(`mistralai`) → `eu`, 미식별 → `global`.
> ² TechCrunch는 `POST /collect/coverage`(`publisher=None`)로 실행 → DB 적재만, 브리핑 없음. Clusterer 완성 전까지 이 상태 유지.

**현황 요약**
- 12개 소스 라이브 (origin 11개 + coverage 1개)
- 도메인 커버리지: `core-lab` 5개(Anthropic·OpenAI·Mistral·Meta·DeepMind) + `core-lab` 1개(Google Research) + `hardware` 1개(NVIDIA) + `ecosystem` 2개 + `academia` 1개 + `community` 1개 + `media` 1개(TechCrunch)
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
5. ~~TechCrunchRssCollector~~ — 첫 `coverage` 소스. `/collect/coverage`(`publisher=None`) store-only 배선. `domain=media` 신규 도입 ✅

남은 작업:
6. **타 컬렉터 function/domain/region 백필** — OpenAI·Anthropic·Mistral·Meta·DeepMind·GitHub·arXiv·HN. 전부 상수라 간단하나 범위 분리됨.
7. **(후순위)** AMD·xAI·Cohere — HTML/피드없음 리스크가 있어 검증 후 진행
8. **(Tier2)** 나머지 coverage 소스 4개(MIT TR·The Verge·MarkTechPost·The Decoder) — 각각 별도 SDD
9. **(Tier2)** Clusterer + Event 모델 설계(§6) → coverage 매칭 활성화

---

## 5. Tier2 — coverage 소스 (앵커 확정)

> function=`coverage`. **항목을 생성하지 않고**, origin 사건에 매칭시켜 "몇 곳이 다뤘나(corroboration_count)"로 중요도를 가산한다.
> 선정 기준: ① 반응형(사건 생성 X, 커버 O) ② echo 밀도 高 ③ 깨끗한 RSS + 타임스탬프.

### 5-1. MVP 채택 — 미디어 5개 ✅

전부 RSS라 기존 `feedparser` 패턴(OpenAI·NVIDIA·GR) 재사용. 수집 메커니즘 동일.

| 소스 | 피드 | domain | region | 성격 | echo 강점 | 상태 |
|---|---|---|---|---|---|---|
| **TechCrunch** | `techcrunch.com/category/artificial-intelligence/feed/` | `media` | `us` | 속보·비즈니스 | 펀딩·런칭 속도, 전문 RSS(페이월 X) | ✅ live (store-only) |
| **MIT Tech Review** | `technologyreview.com/feed/` | `media` | `us` | 분석·에디토리얼 | 권위 → 사건 중요도 신호 | ⏳ 별도 SDD |
| **The Verge (AI)** | `theverge.com/rss/ai-artificial-intelligence/index.xml` | `media` | `us` | 소비자·정책 | 고volume, 커버리지 폭 | ⏳ 별도 SDD |
| **MarkTechPost** | `marktechpost.com/feed/` | `media` | `us` | AI 전문 | **모델 릴리스 요약** = echo 최상 | ⏳ 별도 SDD |
| **The Decoder** | `the-decoder.com/feed/` | `media` | `eu` | AI 연구·비즈니스 | 깨끗한 피드, 연구 커버 | ⏳ 별도 SDD |

### 5-2. 보류 — 이메일 전용 뉴스레터 ⏸

| 소스 | 이유 |
|---|---|
| TLDR AI · The Batch · Rundown · Neuron | **공식 RSS 없음**(이메일 전용) → origin의 죽은 HTML 컬렉터와 같은 벽. MVP 제외 |

### 5-3. 후순위 — Substack 분석형 🔵

| 소스 | 이유 |
|---|---|
| Ahead of AI(Raschka) · Last Week in AI · Simon Willison · The Gradient | RSS는 있으나 **주간·분석형이라 echo 밀도 낮음**. 매칭 검증 후 필요 시 추가 |

---

## 6. Tier2 설계 — 진짜 난제는 수집이 아니라 매칭

> §5 소스 수집은 **쉬운 절반**(RSS 재사용). 어려운 절반은 coverage 기사를 origin 사건에 **묶는 것**.

미착수 설계 항목:
1. **Clusterer + Event 모델** — `Deduplicator→Clusterer` 교체. `Event(대표항목 + corroboration_count + sources[])` 구조. (Mermaid 다이어그램 완료, 코드 미착수)
2. **매칭 방식** — 임베딩 유사도 기준(제목? 요약 포함?)·threshold·라이브러리 선정
3. **coverage 1개 PoC** — TechCrunch만 먼저 붙여 매칭 검증 (5개 일괄 투입 전)
4. **domain 값 확장** — coverage 도입 시 `media`/`newsletter` **신규 domain 값 필요** → 이게 태깅 정책의 나머지 절반(§0 domain 목록에 추가 예정)
5. **스코어 축 재보정** — corroboration_count가 생기면 22.5% baseline 대비 재보정

> ⚠️ 순서 주의: coverage 소스를 매칭 없이 그냥 붙이면 **origin에 섞인 노이즈**가 된다. Clusterer(6-1)가 먼저.

---

## 7. 참고: 컬럼/오피니언 처리

> 컬럼·오피니언(사건 *분석*)은 새 사건이 아니라 coverage로 분류. 단 §5 MVP 미디어에 대체로 포함되므로(MIT TR·The Decoder 등) 별도 소스 추가는 보류.
