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

## 1. 현재 컬렉터 (9개) — Tier 1 완료

| # | 컬렉터 | 소스 | domain | region | function | 수집 방식 | 상태 |
|---|---|---|---|---|---|---|---|
| 1 | AnthropicHtmlCollector | anthropic.com | `core-lab` | `us` | origin | HTML | ✅ live |
| 2 | OpenAIRssCollector | openai.com | `core-lab` | `us` | origin | RSS | ✅ live |
| 3 | MistralHtmlCollector | mistral.ai | `core-lab` | `eu` | origin | HTML | ✅ live |
| 4 | MetaHtmlCollector | ai.meta.com/blog | `core-lab` | `us` | origin | HTML | ✅ live |
| 5 | DeepmindHtmlCollector | deepmind.google | `core-lab` | `us` | origin | HTML | ✅ live |
| 6 | GitHubTrendingCollector | github.com (Trending) | `ecosystem` | `global` | origin | HTML | ✅ live |
| 7 | HuggingFaceApiCollector | huggingface.co | `ecosystem` | `global` | origin | API | ✅ live |
| 8 | ArxivApiCollector | arxiv.org | `academia` | `global` | origin | API | ✅ live |
| 9 | HackerNewsApiCollector | news.ycombinator.com | `community` | `global` | origin | Firebase API | ✅ live |

**현황 요약**
- 7개 소스 라이브, DB 1,200+ rows, 파이프라인 e2e 동작
- 편중: `core-lab` 5개 쏠림 / `hardware` 0개 / 중국 랩 0개
- HTML 파싱(1·3·4·5·6)은 구조 변경 시 취약 → 유지보수 부채

---

## 2. 신규 제안 컬렉터

### 2-1. 실제로 신설할 것 (2개)

| 제안 컬렉터 | 소스 | domain | region | function | 수집 방식 | 난이도 | 피드 URL |
|---|---|---|---|---|---|---|---|
| **NvidiaRssCollector** | developer.nvidia.com | `hardware` | `us` | origin | **RSS** | 🟢 쉬움 | `developer.nvidia.com/blog/feed` |
| **GoogleResearchRssCollector** | research.google | `core-lab` | `us` | origin | **RSS** | 🟢 쉬움 | `research.google/blog/rss` |

> 둘 다 OpenAI RSS 컬렉터(#2) 패턴을 그대로 재사용. `feedparser` 기반, A0에서 실제 응답 1건 덤프 후 파서 확정.

### 2-2. 후순위 (HTML/피드없음 — 리스크 있어 나중에)

| 제안 컬렉터 | 소스 | domain | region | function | 수집 방식 | 난이도 |
|---|---|---|---|---|---|---|
| AmdCollector | amd.com | `hardware` | `us` | origin | HTML 추정 | 🟡 중간 |
| CohereCollector | cohere.com | `core-lab` | `ca` | origin | HTML | 🟡 중간 |
| xAICollector | x.ai | `core-lab` | `us` | origin | 피드 없음 (X 중심) | 🔴 어려움 |

---

## 3. 중국 프론티어 랩 — 개별 컬렉터 만들지 않음

DeepSeek · Qwen(Alibaba) · GLM(Zhipu) · Kimi(Moonshot) 는 **자체 공개 RSS가 없다.**
개별 스크래퍼로 가면 죽은 HTML 컬렉터 5개와 같은 벽에 부딪힌다.

**대신: 기존 HuggingFace 컬렉터(#7)로 흡수한다.**
- 근거: 중국 랩 모델 릴리스는 HuggingFace·GitHub에 집중 배포됨 (Qwen 단독 HF 파생 모델 18만+, 주간 신규 인기 모델 상위권 상시 점유)
- 방법: HF 컬렉터가 잡은 항목에 **조직명 매칭으로 `region=cn` 태그 부착** 로직만 추가

| 랩 | 모델군 | 처리 방침 | 태그 |
|---|---|---|---|
| DeepSeek | DeepSeek V4 | HF 흡수 | `core-lab` / `cn` |
| Alibaba | Qwen | HF 흡수 | `core-lab` / `cn` |
| Zhipu (Z.ai) | GLM | HF 흡수 | `core-lab` / `cn` |
| Moonshot | Kimi | HF 흡수 | `core-lab` / `cn` |

> 스크래퍼 4개 유지보수를 태그 로직 1개로 대체. "소스 늘리려다 죽은 컬렉터 4개 추가" 회피.

---

## 4. 우선순위 & 다음 작업

1. **태그 필드 3개 확정** — `function` / `domain` / `region`을 소스 레지스트리(또는 `CollectedItem.metadata`)에 추가
2. **NvidiaRssCollector SDD** — 첫 타자. OpenAI RSS 패턴 복사 + `domain=hardware`. A0에서 RSS 응답 덤프
3. **HF 컬렉터 `region=cn` 태깅** — 조직명 매칭으로 중국 랩 커버 완료
4. **GoogleResearchRssCollector** — NVIDIA 검증 후 같은 패턴으로 빠르게
5. **(후순위)** AMD·xAI·Cohere — HTML/피드없음 리스크가 있어 검증 후 진행

---

## 5. 참고: 스코어보드(coverage) 소스 — 아직 미착수

> function=`coverage`. origin 사건의 중요도를 측정하는 교차보도 풀. Tier2 설계 시 확정 예정.

- 뉴스레터: TLDR · The Batch · Rundown 등
- 미디어: TechCrunch · Wired · MIT Tech Review 등
- 컬럼/오피니언: (coverage로 분류 — 새 사건이 아니라 사건 분석)

> 미해결 질문: coverage 풀을 뉴스레터로 좁힐지, 미디어까지 넓힐지 → Tier2 설계의 핵심 병목.
