# NVIDIA Collector 리뷰

작성일: 2026-07-01

## 요약

이번 변경은 NVIDIA Developer Blog RSS 기반 컬렉터를 추가하고 `/collect` 실행 대상에 `"nvidia": NvidiaRssCollector()`를 등록하는 작업이다. NVIDIA는 `source="NVIDIA"`, `MAX_ITEMS=50`, `metadata.function/domain/region/feed`를 고정값으로 넣고, RSS의 `entry.tags`를 `tags`에 반영한다.

## 주요 리뷰 의견

### 1. 현재 환경에서는 NVIDIA 테스트와 전체 테스트가 실행되지 않음

- 위치: `tests/test_nvidia_collector_golden.py`
- 확인 명령: `python3 -m pytest tests/test_nvidia_collector_golden.py -q`
- 실제 결과: `ModuleNotFoundError: No module named 'feedparser'`

`NvidiaRssCollector`는 import 시점에 `feedparser`가 필요하다. 현재 Python 환경에는 `feedparser`가 없어 NVIDIA 테스트가 collection 단계에서 실패한다. 같은 이유로 `/collect` 라우터도 `NvidiaRssCollector` import 시점에 깨질 수 있다.

필요 조치:

- 현재 실행 환경에 `requirements.txt`가 실제로 설치되어 있는지 확인한다.
- `feedparser` 설치 후 NVIDIA 테스트를 다시 실행한다.
- 앱 실행 환경과 테스트 환경이 같은 dependency set을 쓰도록 맞춘다.

### 2. `PROGRESS.md`의 `50 passed` 기록이 현재 repo 상태로 재현되지 않음

- 위치: `PROGRESS.md`
- 문서 내용: `50 passed`
- 실제 확인 명령: `python3 -m pytest -q`
- 실제 결과: arXiv/NVIDIA 테스트가 모두 `feedparser` import error로 중단

문서에는 NVIDIA golden fixture와 전체 회귀가 통과한 것으로 적혀 있지만, 현재 환경 기준으로는 테스트가 시작 단계에서 실패한다.

권장:

- 통과한 환경과 명령을 명시하거나, 현재 환경에서 재현 가능하게 의존성을 먼저 정리한다.
- 재검증 후 `PROGRESS.md`의 passed count를 유지한다.

### 3. RSS tag 파싱이 필드 누락에 약함

- 위치: `app/infrastructure/collectors/nvidia_rss_collector.py:35-37`

현재 코드는 `categories = [t["term"].lower() for t in raw_tags]`로 직접 인덱싱한다. feedparser가 예상과 다른 tag object를 반환하거나 일부 tag에 `term`이 없으면 한 entry 때문에 수집 전체가 `KeyError`로 중단될 수 있다.

권장:

- `term = t.get("term")` 형태로 방어적으로 처리한다.
- 빈 term은 제외한다.

### 4. RSS summary의 HTML 혼입을 그대로 저장하는 결정은 downstream 영향 확인이 필요함

- 위치: `app/infrastructure/collectors/nvidia_rss_collector.py:45`

SDD와 PROGRESS에는 summary HTML 혼입을 원문 그대로 두는 것으로 되어 있다. MVP로는 가능한 결정이지만, Discord briefing이나 검색/스코어링에서 HTML 태그가 그대로 노출될 수 있다.

권장:

- 최소한 UI/Discord 출력에서 HTML이 그대로 보이지 않는지 확인한다.
- 원문 보존이 필요하면 `metadata`에 raw summary를 두고 `summary`는 text normalize하는 방식도 검토한다.

## 잘된 점

- 공식 RSS를 사용해 scraping 리스크가 낮다.
- OpenAI RSS collector와 같은 패턴을 재사용해 구현이 단순하다.
- `MAX_ITEMS=50`으로 RSS 100건 응답을 제한해 수집 볼륨을 통제했다.
- `metadata`에 `function`, `domain`, `region`, `feed`를 넣어 hardware origin 소스라는 성격을 명확히 남겼다.
- `/collect` 등록 변경이 import와 dict 한 줄 추가 수준으로 작게 유지되었다.

## 검증 결과

- `python3 -m pytest tests/test_nvidia_collector_golden.py -q`
  - 결과: `ModuleNotFoundError: No module named 'feedparser'`
- `python3 -m pytest -q`
  - 결과: arXiv/NVIDIA 테스트 `feedparser` import error로 중단

현재 기준으로 NVIDIA collector 테스트와 전체 테스트 통과는 확인하지 못했다. 먼저 dependency 환경을 맞추는 것이 필요하다.
