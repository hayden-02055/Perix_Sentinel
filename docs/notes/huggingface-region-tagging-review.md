# HuggingFace Region Tagging 리뷰

작성일: 2026-07-01

## 요약

이번 변경은 `HuggingFaceApiCollector`에 `function=origin`, `domain=ecosystem`, `region=<파생값>` 메타데이터를 추가하는 작업이다. region은 author 조직 핸들 정확 매칭을 먼저 보고, 실패하면 model id substring으로 보조 판정한 뒤, 둘 다 실패하면 `global`로 둔다.

## 주요 리뷰 의견

### 1. HF 골든 테스트가 실제 실행되지 않고 전부 skipped 됨

- 위치: `tests/test_huggingface_collector_golden.py`
- 확인 명령: `python3 -m pytest tests/test_huggingface_collector_golden.py -q`
- 실제 결과: `6 skipped, 14 warnings`

`pytest.mark.asyncio`가 현재 환경에서 인식되지 않아 async 테스트가 실행되지 않는다. 따라서 region 파생 로직을 검증하려는 6개 테스트가 현재는 보호막 역할을 하지 못한다.

필요 조치:

- `pytest-asyncio`가 현재 테스트 런타임에 설치되어 import 가능한지 확인한다.
- pytest 설정(`asyncio_mode`, `asyncio_default_fixture_loop_scope`)을 현재 pytest/pytest-asyncio 버전에 맞춘다.
- HF 테스트가 `6 passed`로 실제 실행되는지 재확인한다.

### 2. `PROGRESS.md`의 `58 passed` 기록이 현재 repo 상태로 재현되지 않음

- 위치: `PROGRESS.md`
- 문서 내용: `58 passed`
- 실제 확인 명령: `python3 -m pytest -q`
- 실제 결과: arXiv/Google Research/NVIDIA 테스트가 `feedparser` import error로 collection 단계에서 중단

현재 환경 기준으로 전체 테스트는 시작 단계에서 실패한다. 따라서 `PROGRESS.md`의 passed count는 재현 가능한 상태가 아니다.

권장:

- 테스트가 통과한 환경과 명령을 명시한다.
- 현재 repo 환경에서도 재현 가능하게 dependency를 정리한다.

### 3. substring 기반 region 판정은 오분류 가능성이 있음

- 위치: `app/infrastructure/collectors/huggingface_api_collector.py:63-88`

1차 author exact match는 비교적 안전하지만, 2차 `_FAMILY_REGION` substring은 오분류 가능성이 있다. 예를 들어 `phi`, `glm`, `yi-`, `mistral` 같은 문자열이 모델명 안에 다른 의미로 포함될 수 있고, 커뮤니티 모델명이 여러 family 이름을 동시에 포함하면 먼저 매칭된 region이 선택된다.

권장:

- substring 판정으로 region이 정해진 경우 metadata에 `"region_signal": "family"` 같은 근거를 남기는 것을 검토한다.
- 충돌 가능성이 있는 이름은 더 구체적인 패턴으로 제한한다.
- 운영 샘플에서 family 기반 판정 비율과 오분류 사례를 주기적으로 확인한다.

### 4. `baidu`를 미결로 남긴 결정은 의도적이지만 누락 비용이 있음

- 위치: `PROGRESS.md` 미결 결정사항

A0에서 `baidu/Unlimited-OCR`이 관측됐지만 `_ORG_REGION`에는 추가하지 않았다. 문서에 미결로 남긴 것은 투명하지만, 이미 관측된 중국 조직이면 다음 변경을 기다리는 동안 계속 `global`로 태깅된다.

권장:

- 의도적으로 제외한 근거가 없다면 `_ORG_REGION["baidu"] = "cn"` 추가를 검토한다.
- 미결로 유지한다면 언제 확장할지 기준을 정한다.

## 잘된 점

- 중국 랩을 개별 scraper로 늘리지 않고 HuggingFace metadata 태깅으로 흡수한 방향은 유지보수 비용이 낮다.
- author exact match를 1차 신호로 두고, 재업로드를 model family substring으로 구제하는 2단계 구조는 현실적인 절충이다.
- `function`, `domain`, `region`을 metadata에 넣어 NVIDIA/Google Research 쪽 태그 체계와 맞추기 시작했다.
- HF 전용 골든 fixture를 추가해 region 케이스를 고정하려는 방향은 좋다. 테스트 실행 환경만 정리되면 유용한 회귀 방어가 된다.

## 검증 결과

- `python3 -m pytest tests/test_huggingface_collector_golden.py -q`
  - 결과: `6 skipped, 14 warnings`
- `python3 -m pytest -q`
  - 결과: arXiv/Google Research/NVIDIA 테스트 `feedparser` import error로 중단

현재 기준으로 HF region 테스트와 전체 테스트 통과는 확인하지 못했다. 먼저 async pytest 설정과 dependency 환경을 맞추는 것이 필요하다.
