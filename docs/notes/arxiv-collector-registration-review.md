# arXiv Collector 등록 리뷰

작성일: 2026-07-01

## 요약

이번 변경은 arXiv 컬렉터를 추가하고 `/collect` 실행 대상에 `"arxiv": ArxivApiCollector()`를 등록하는 작업이다. `PROGRESS.md`에는 arXiv SDD 진행 상황, 골든 fixture 테스트, 향후 `/collect` 실가동 단계가 정리되었다.

## 주요 리뷰 의견

### 1. 현재 환경에서는 테스트가 실행되지 않고 collection 단계에서 실패함

- 위치: `tests/test_arxiv_collector_golden.py`
- 확인 명령: `python3 -m pytest tests/test_arxiv_collector_golden.py -q`
- 실제 결과: `ModuleNotFoundError: No module named 'feedparser'`

`requirements.txt`에는 `feedparser==6.0.11`이 있지만, 현재 실행 중인 Python 환경에는 설치되어 있지 않다. 이 상태에서는 arXiv 테스트뿐 아니라 `app/interface/api/collect.py`가 `ArxivApiCollector`를 import하는 순간 `/collect` 라우터 import도 실패할 수 있다.

필요 조치:

- 현재 venv 또는 실행 환경에 `requirements.txt`가 실제로 설치되어 있는지 확인한다.
- CI/로컬 실행 명령을 동일하게 맞춘다.
- 의존성 설치 후 `python3 -m pytest tests/test_arxiv_collector_golden.py -q`를 다시 실행한다.

### 2. `PROGRESS.md`의 테스트 결과가 현재 검증 결과와 맞지 않음

- 위치: `PROGRESS.md`
- 문서 내용: `46 passed`
- 실제 확인 명령: `python3 -m pytest -q`
- 실제 결과: arXiv 테스트 import error로 중단

문서에는 arXiv 골든 fixture 테스트까지 통과한 것으로 기록되어 있지만, 현재 환경에서는 `feedparser` import error 때문에 전체 테스트가 시작 단계에서 실패한다.

권장:

- 실제 테스트가 통과한 환경과 명령을 명시한다.
- 현재 repo 기준으로 재현 가능한 상태가 된 뒤 `46 passed` 기록을 유지한다.

### 3. arXiv entry 필드 접근이 일부 필드 누락에 약함

- 위치: `app/infrastructure/collectors/arxiv_api_collector.py:50-60`

현재 코드는 `tags`와 `authors` 항목에 대해 `t["term"]`, `a["name"]`으로 직접 접근한다. feedparser 응답이 예상과 다르거나 일부 항목이 빠지면 수집 전체가 `KeyError`로 중단될 수 있다.

권장:

- `t.get("term")`, `a.get("name")` 기반으로 방어적으로 처리한다.
- 빈 값은 제외해 한 엔트리의 부분 필드 누락이 전체 수집 실패로 번지지 않게 한다.

## 잘된 점

- arXiv를 `CollectorPort` 구현으로 추가해 기존 수집 구조에 자연스럽게 맞췄다.
- `max_results=50`, `cs.AI/cs.CL/cs.LG` 카테고리 제한을 모듈 상수로 둬 볼륨 폭주를 막는 의도가 명확하다.
- title/summary 공백 정규화가 들어가 Atom XML 특유의 줄바꿈 문제를 줄였다.
- `/collect` 등록은 한 줄 추가 수준으로 작게 유지되어 변경 범위가 좁다.

## 검증 결과

- `python3 -m pytest tests/test_arxiv_collector_golden.py -q`
  - 결과: `ModuleNotFoundError: No module named 'feedparser'`
- `python3 -m pytest -q`
  - 결과: arXiv 테스트 collection error로 중단

현재 리뷰 기준으로는 테스트 통과를 확인하지 못했다. 먼저 실행 환경의 의존성 설치 상태를 맞추는 것이 필요하다.
