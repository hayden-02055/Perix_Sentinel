# Perix Sentinel — HuggingFace Region Tagging SDD

> Software Design Document · v0.1
> 목적: **기존 `HuggingFaceApiCollector`에 `region` 파생 로직을 추가한다.** 중국 프론티어 랩(DeepSeek·Qwen·GLM·Kimi 등)을 별도 컬렉터 없이 HF 항목에 `region=cn` 태그로 흡수.
> 성격: **신규 컬렉터가 아니라 기존 컬렉터 수정.** 선행: origin 11개 적재 중(NVIDIA·Google Research A4 완료).

---

## 0. 한 줄 요약

HF 컬렉터는 이미 `author`(조직 핸들)를 추출해 metadata에 넣고 있다. 여기에 **조직 핸들 → region 매핑**을 붙여, 각 항목에 `region`을 파생시킨다. 이것으로 **중국 랩 개별 스크래퍼 4개를 만들지 않고** HF가 이들을 간접 커버한다. **region은 이 프로젝트에서 처음으로 "상수가 아니라 데이터에서 파생되는" 태그**다(NVIDIA·GR은 컬렉터 고정값이었음). **스코어링은 비범위.**

---

## 1. 맥락: 왜 컬렉터 수정인가

COLLECTORS.md에서 결정한 방침:
- 중국 랩은 자체 RSS가 없고 HuggingFace·GitHub에 집중 배포된다.
- → 개별 컬렉터 대신 **기존 HF 컬렉터가 잡은 항목에 `region=cn` 태그를 부착**한다.

이 SDD는 그 "태그 부착 로직"을 실제로 구현하기 위한 설계다. 스크래퍼 4개 유지보수를 **매핑 상수 1개 + 파생 함수 1개**로 대체한다.

---

## 2. 목표 (Goals)

1. HF 각 항목의 `author`(및 보조로 model_id)로부터 **`region`을 파생**해 `metadata["region"]`에 넣는다.
2. 알려진 **중국 조직 핸들**(DeepSeek·Qwen·Zhipu·Moonshot 등)을 `cn`으로 정확히 태깅한다.
3. HF 컬렉터에 **`function=origin`, `domain=ecosystem`** 태그도 함께 부착(NVIDIA·GR과 태그 체계 일관성).
4. 재업로드(커뮤니티 GGUF 등)를 위한 **보조 신호**(모델명 substring)를 둔다.
5. 알 수 없는 조직은 **`global`을 기본값**으로 둔다(HF의 전역 허브 성격 반영, COLLECTORS.md 기본값과 일치). 아는 조직만 `cn/us/eu`로 오버라이드.
6. **없던 HF 골든 테스트를 이번에 추가**한다(tag 출력을 바꾸므로 회귀 방어 필수).

---

## 3. 비목표 (Non-Goals)

- **스코어링 반영** — `region`을 popularity/가중치에 쓰지 않는다. 지금은 **태그 부착까지만**. (Tier2 재보정 시 활용)
- **전 세계 조직 완전 매핑** — 모든 HF 조직을 region으로 분류하지 않는다. **cn을 확실히 잡는 것이 1차 목표**, 주요 us/eu 몇 개는 정확도용으로만.
- **다른 컬렉터로의 region 백필** — OpenAI·arXiv·HN 등 기존 컬렉터에 region을 소급 부착하는 건 별건(§8 다음 작업으로 분리).
- **`CollectedItem` 스키마 변경** — region은 기존 `metadata` dict에 넣는다.
- **국가 판별 고도화** — GeoIP·조직 DB 연동 없음. 정적 매핑 상수만.

---

## 4. 설계

### 4.1 region 파생 로직 (2단계 신호)

HF의 `author = model_id.split("/")[0]`는 **조직이 직접 올렸을 때만** 신뢰할 수 있다.
`bartowski/Qwen2.5-GGUF` 같은 재업로드는 author가 `bartowski` → 조직 매핑만으론 놓친다.
→ **2단계 신호**로 처리:

| 우선순위 | 신호 | 신뢰도 | 방식 |
|---|---|---|---|
| 1차 | `author` 핸들 **정확 일치** | 높음 | `_ORG_REGION`에서 핸들 조회 |
| 2차 | `model_id` **substring** (모델 패밀리) | 중간 | 1차 실패 시 `_FAMILY_REGION`에서 부분 매칭 |
| 폴백 | 둘 다 미스 | — | `region = "global"` (HF 기본값) |

> 1차가 잡히면 2차는 건너뛴다. 재업로드만 2차로 구제.

### 4.2 매핑 상수 (컬렉터 모듈에 정의)

```python
# 조직 핸들 → region  (정확 일치, 소문자 비교)
_ORG_REGION: dict[str, str] = {
    # ── China ──
    "deepseek-ai": "cn",
    "qwen": "cn",              # Alibaba
    "zai-org": "cn",           # Z.ai / Zhipu
    "thudm": "cn",             # 구 GLM (Tsinghua)
    "zhipuai": "cn",
    "moonshotai": "cn",        # Kimi
    "01-ai": "cn",             # Yi
    "baichuan-inc": "cn",
    "internlm": "cn",
    "tencent": "cn",           # Hunyuan
    "bytedance-seed": "cn",
    "minimaxai": "cn",
    "stepfun-ai": "cn",
    "openbmb": "cn",           # MiniCPM
    "xiaomimimo": "cn",
    # ── US ── (정확도용 최소)
    "meta-llama": "us",
    "google": "us",
    "microsoft": "us",
    "openai": "us",
    "nvidia": "us",
    # ── EU ──
    "mistralai": "eu",
}

# 모델 패밀리 substring → region  (재업로드 구제, 2차)
_FAMILY_REGION: list[tuple[str, str]] = [
    ("deepseek", "cn"),
    ("qwen", "cn"),
    ("glm", "cn"),
    ("kimi", "cn"),
    ("yi-", "cn"),
    ("baichuan", "cn"),
    ("internlm", "cn"),
    ("minicpm", "cn"),
    ("llama", "us"),
    ("gemma", "us"),
    ("phi", "us"),
    ("mistral", "eu"),
    ("mixtral", "eu"),
]
```

> 상수는 **유지보수 대상**임을 주석으로 명시. 새 중국 랩 등장 시 여기만 추가.

### 4.3 파생 함수

```python
def _derive_region(author: str, model_id: str) -> str:
    a = author.lower().strip()
    if a in _ORG_REGION:                 # 1차: 조직 핸들 정확 일치
        return _ORG_REGION[a]
    mid = model_id.lower()               # 2차: 모델명 substring
    for needle, region in _FAMILY_REGION:
        if needle in mid:
            return region
    return "global"                      # 폴백: HF 전역 허브 기본값
```

### 4.4 metadata 부착 (일관성)

기존 metadata에 태그 3종 추가(NVIDIA·GR과 동일 체계, HF는 API라 `feed` 키 없음):

```python
metadata = {
    "likes": likes,
    "downloads": downloads,
    "pipeline_tag": pipeline_tag or "",
    "author": author,
    # ── 신규 ──
    "function": "origin",
    "domain":   "ecosystem",
    "region":   _derive_region(author, model_id),
}
```

> 선택: `region != "global"`일 때(즉 특정 지역으로 식별됐을 때)만 `tags`에도 `f"region:{region}"`을 추가해 flat 필터를 쉽게 할지 A 결정. 기본은 metadata만.

---

## 5. 절차

| 단계 | 내용 |
|---|---|
| **A0 관측** | HF trending 응답에서 실제 `author` 핸들 표기 확인(`deepseek-ai`? `deepseek`? 대소문자?). 중국 모델이 실제로 trending에 잡히는지, author가 조직인지 재업로더인지 표본 확인 |
| **A1 상수** | `_ORG_REGION`·`_FAMILY_REGION`을 A0 관측 표기에 맞춰 확정 |
| **A2 함수** | `_derive_region` 추가, `collect()`에서 metadata에 `function/domain/region` 부착 |
| **A3 테스트** | **HF 골든 fixture 신규 작성** + region 케이스 검증(§6) |
| **A4 실가동** | `/collect` 실행, 중국 모델이 `region=cn`으로 적재되는지 DB 확인 |

---

## 6. 테스트 계획 (HF 골든 신규 + region 케이스)

HF는 골든 테스트가 **없으므로 이번에 신설**. `fetch_json`을 모킹하는 방식(HN 골든의 `mock_http` 참고).

- **fixture**: `tests/fixtures/huggingface_trending.json` (실제 `recentlyTrending` 응답 스냅샷, 4~5건 트림)
- **케이스 매트릭스** (region 로직 검증):

| 케이스 | author / model_id | 기대 region | 검증 신호 |
|---|---|---|---|
| 중국 조직 직접 | `deepseek-ai/DeepSeek-V4` | `cn` | 1차(조직) |
| 중국 재업로드 | `bartowski/Qwen2.5-GGUF` | `cn` | 2차(substring) |
| 미국 조직 | `meta-llama/Llama-4` | `us` | 1차 |
| 미지 조직 | `randomuser/some-model` | `global` | 폴백 |

- **비교 필드**: `source / title / url / tags / metadata`(특히 `metadata["region"]`)
- `published_at`: 기존 golden 패턴대로 isoformat 비교

---

## 7. Definition of Done

- [ ] `_ORG_REGION`·`_FAMILY_REGION` 상수 정의, 유지보수 주석 포함
- [ ] `_derive_region(author, model_id)` 함수 추가, 2단계 신호 + `global` 폴백
- [ ] `metadata`에 `function=origin`·`domain=ecosystem`·`region=<파생>` 부착
- [ ] A0에서 실제 HF author 핸들 표기 확인 후 상수 확정 (`docs/notes` 기록)
- [ ] **HF 골든 fixture 신규 작성** + region 4케이스(cn조직/cn재업로드/us/global) 검증
- [ ] 전체 테스트 그린
- [ ] `/collect` 실가동, 중국 모델 `region=cn` 적재 육안 확인
- [ ] **스코어링 파일 무수정** (region은 태그일 뿐, 가중치 미반영)
- [ ] 기존 HF 항목의 다른 필드(tags·likes·downloads) **회귀 없음** 확인
- [ ] PROGRESS에 "HF region 파생 추가 / 타 컬렉터 region 백필은 별건" 기록

---

## 8. 다음 작업 (분리)

- **타 컬렉터 region 백필** — OpenAI(`us`)·arXiv(`global`)·HN(`global`) 등 기존 컬렉터에 `function/domain/region` 태그 소급 부착. HF와 달리 전부 상수라 간단하지만 범위 분리.
- **domain 세분** — HF `ecosystem` 안에서 중국 랩은 사실상 `core-lab` 성격 → domain을 재파생할지 여부는 Tier2 설계 때 재논의.

---

## 부록: 참고 실제 코드

- `app/infrastructure/collectors/huggingface_api_collector.py` — 수정 대상. `author` 추출부·`_build_tags`·metadata 구성 확인
- `app/infrastructure/collectors/hackernews_api_collector.py` — `fetch_json` 모킹·필터 상수 패턴
- `tests/test_hackernews_collector_golden.py` — `mock_http` 기반 골든(HF 골든 신설 시 참고)
- `app/domain/models/collected_item.py` — `metadata` dict
