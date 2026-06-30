# Anthropic Collector 구현 회고

관련 PRD: [Anthropic RSS Collector](<../PRD/collecting/Anthropic RSS Collector.md>)

작성일: 2026-05-18

## 요약

PRD는 **RSS 기반 수집**을 명시했지만, Anthropic 공식 사이트가 RSS 피드를 제공하지 않아 **HTML 스크래핑** 방식으로 전환하여 구현했다.

## 1. 실패한 시도 — RSS

### 1차: PRD에 적힌 URL 그대로
- URL: `https://www.anthropic.com/news/rss.xml`
- 결과: **HTTP 404**, Next.js 에러 페이지(HTML) 반환
- `feedparser` 동작:
  ```
  Feed parse warning: <unknown>:2:3549: not well-formed (invalid token)
  Collected 0 items from Anthropic RSS
  ```
  HTML을 XML로 파싱하려다 `bozo=True`가 되고 엔트리 0개로 끝남.

### 2차: 후보 URL 탐색
다음 8개 후보 모두 **404 + Next.js 에러 페이지** 반환.

| URL | 결과 |
|---|---|
| `https://www.anthropic.com/rss.xml` | 404 |
| `https://www.anthropic.com/news/feed` | 404 |
| `https://www.anthropic.com/news/feed.xml` | 404 |
| `https://www.anthropic.com/feed` | 404 |
| `https://www.anthropic.com/feed.xml` | 404 |
| `https://www.anthropic.com/research/rss.xml` | 404 |
| `https://anthropic.com/news/rss.xml` | 404 |
| `https://www.anthropic.com/news.rss` | 404 |

### 3차: HTML 자동 발견 태그 확인
- `https://www.anthropic.com/`, `https://www.anthropic.com/news` HTML 본문에서
  - `<link rel="alternate" type="application/rss+xml">` 태그 없음
  - `href`에 `rss` 또는 `feed`를 포함하는 링크 없음

**결론:** 현시점 Anthropic 공식 사이트는 공개 RSS 피드를 제공하지 않는다.

## 2. 해결 — HTML 스크래핑

`https://www.anthropic.com/news` 페이지를 `httpx`로 가져와 `BeautifulSoup`으로 카드 anchor를 파싱하는 방식으로 전환.

### 카드 구조 — 두 가지 형태
`/news` 페이지의 항목은 동일한 anchor 패턴이 아니라, **두 가지 다른 스타일의 카드**가 섞여 있었다.

| 형태 | 클래스 식별자 | 제목 위치 | 시간 | 요약 |
|---|---|---|---|---|
| Featured | `FeaturedGrid-module-*` | `<h2>` / `<h4>` | `<time>` | `<p>` |
| PublicationList | `PublicationList-module-*` | `<span class="...title...">` | `<time>` | 없음 |

처음에는 `find(["h1","h2",...,"h5"])`로만 제목을 찾아 PublicationList 카드가 전부 누락되어 **13개 중 3개만 수집**되었다. 셀렉터를 다음처럼 보강해서 두 형태 모두 잡도록 했다.

```python
title_el = (
    anchor.find(["h1", "h2", "h3", "h4", "h5"])
    or anchor.select_one('[class*="title"]')
)
```

> **참고:** Anthropic 사이트는 Next.js + CSS Modules를 쓰기 때문에 클래스가 `PublicationList-module-scss-module__KxYrHG__title`처럼 빌드별 해시를 포함한다. `[class*="title"]` 부분 일치 셀렉터는 소스 클래스명만 유지되면 살아남는다.

### 최종 동작 검증

| 단계 | 결과 |
|---|---|
| 컬렉터 단독 실행 | 13개 항목 수집 (Featured 3 + PublicationList 10) |
| Use case 1차 (빈 DB) | `{'total_collected': 13, 'new_items': 13}` |
| Use case 2차 (재실행) | `{'total_collected': 13, 'new_items': 0}` — URL Hash 중복 제거 정상 |

## 3. 최종 변경

- 신규: [app/infrastructure/collectors/anthropic_html_collector.py](../../app/infrastructure/collectors/anthropic_html_collector.py)
- 수정: [app/interface/api/collect.py](../../app/interface/api/collect.py) — `/collect` 엔드포인트에서 OpenAI + Anthropic 모두 실행
- 삭제: `anthropic_rss_collector.py` — 404 RSS URL 기반의 무효 코드

## 4. 알려진 한계 / 후속 과제

- **마크업 변경 취약성:** Anthropic이 `/news` 페이지 구조를 바꾸면 셀렉터를 손봐야 한다. RSS와 달리 깨졌을 때 즉시 감지되지 않을 수 있다 → 향후 모니터링/알람 필요.
- **요약 누락:** PublicationList 카드에는 본문 요약 `<p>` 자체가 없어 `summary=""`로 저장된다. 상세 페이지를 추가 fetch하면 채울 수 있으나 비용 발생.
- **수집 범위:** `/news` 첫 페이지만 본다. 페이지네이션은 미구현.
- **RSS 복귀 가능성:** Anthropic이 공식 RSS를 제공하거나, 내부적으로 알려진 비공개 RSS URL이 확인되면 RSS 컬렉터로 교체하는 편이 마크업 의존성을 제거해 더 견고하다.
