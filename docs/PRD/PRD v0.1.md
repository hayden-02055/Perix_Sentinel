# Perix Sentinel — PRD v0.1

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **프로젝트명** | Perix Sentinel |
| **한 줄 정의** | AI/Tech 트렌드를 자동 수집·분석·요약하여 브리핑해주는 인텔리전스 시스템 |

### 목표

> AI 엔지니어, 리서처, 개발자들이 **"정보 과부하 없이 핵심 변화만 빠르게 파악"** 할 수 있도록 한다.

---

## 2. 해결하려는 문제

현재 AI 정보는:

- 너무 빠르게 생성됨
- 플랫폼이 분산되어 있음
- 노이즈가 많음
- 한국어 요약이 부족함
- 핵심 중요도를 판단하기 어려움

**주요 정보 소스 예시:**

- GitHub Trending
- arXiv
- Hugging Face
- OpenAI Blog
- Reddit
- Hacker News

사용자는 매일 수십 개 사이트를 돌아다녀야 한다. **Perix Sentinel은 이를 자동화한다.**

---

## 3. MVP 목표

### 핵심 기능

#### 1. 데이터 수집

RSS/API 기반 수집. 초기 대상:

- OpenAI News
- Anthropic News
- Hugging Face Blog
- GitHub Trending
- arXiv AI
- Reddit AI 커뮤니티

#### 2. 데이터 정규화

모든 데이터를 공통 포맷으로 변환:

```json
{
  "source": "OpenAI",
  "title": "...",
  "url": "...",
  "summary": "...",
  "published_at": "...",
  "tags": []
}
```

#### 3. 중복 제거

동일 기사/링크 제거. 전략:

- URL hash
- title similarity

#### 4. AI 요약

LLM 기반 한국어 요약. 출력 항목:

- 핵심 요약
- 왜 중요한지
- 산업 영향

#### 5. 브리핑 전송

초기 채널:

- Discord Webhook
- Telegram Bot

---

## 4. MVP 제외 범위

초기에는 제외:

- 웹 대시보드
- 사용자 로그인 / 결제 시스템
- RAG / Vector DB
- LangGraph Agent
- Fine-tuning / 추천 알고리즘
- 실시간 스트리밍 / AI 자동 평가

---

## 5. 핵심 아키텍처

```
[RSS / API]
     ↓
Collector Layer
     ↓
Normalizer
     ↓
Deduplicator
     ↓
AI Summarizer
     ↓
Publisher
(Discord / Telegram)
```

---

## 6. 기술 스택

### Backend

| 항목 | 선택 | 이유 |
|------|------|------|
| Language | **Python 3.12** | AI 생태계 최강, async 처리 우수 |
| Framework | **FastAPI** | LangChain/LangGraph 연결 용이, RSS/API 작업 편의 |

### AI Layer

| 항목 | 선택 |
|------|------|
| LLM API | **OpenAI API** (초기) |
| Orchestration | **LangChain** (얇게만) |

> **LangGraph는 초기에 제외.** 현재 workflow가 단순하고, orchestration이 과하면 MVP 속도가 느려진다.

### Data Collection

| 용도 | 라이브러리 |
|------|-----------|
| RSS | `feedparser` |
| HTTP | `httpx` |
| HTML Parsing | `beautifulsoup4` |

### Database

| 단계 | 선택 | 이유 |
|------|------|------|
| MVP | **SQLite** | 빠름, 비용 0, 배포 쉬움 |
| 이후 | PostgreSQL + pgvector | 확장성 |

### Scheduler

**APScheduler** — FastAPI 궁합이 좋고, cron보다 Python-native하며 관리가 편하다.

### Deployment

**Docker + docker-compose**

```
Ubuntu Server
 └── Docker
      └── Perix Sentinel Container
```

> Ubuntu, Docker, Nginx, SSH 경험을 그대로 활용.

### Messaging

| 채널 | 방식 | 비고 |
|------|------|------|
| **Discord** | Webhook | 구현 5분컷, 디버깅 편함 — 초기 추천 |
| Telegram | Bot API | 이후 추가 |

---

## 7. 디렉토리 구조

```
perix-sentinel/
├── app/
│   ├── collectors/
│   ├── normalizers/
│   ├── summarizers/
│   ├── publishers/
│   ├── schedulers/
│   ├── domain/
│   └── main.py
│
├── tests/
├── docker/
├── requirements.txt
├── docker-compose.yml
└── README.md
```

---

## 8. MVP 성공 기준

MVP 성공 조건:

- [x] 매일 자동 실행됨
- [x] AI 뉴스 수집 성공
- [x] 중복 제거 성공
- [x] 한국어 요약 성공
- [x] Discord 자동 브리핑 성공

> **"아침에 일어나면 AI 브리핑이 와있다."**
>
> 이 상태가 MVP 성공.

---

## 9. 이후 확장 방향

### Phase 2

- 웹 대시보드
- 검색 기능
- 태그 시스템
- 이메일 브리핑

### Phase 3

- LangGraph Agent
- RAG
- 벡터 검색
- 개인화 추천

### Phase 4

- 자체 모델 파인튜닝
- Ontology 기반 Knowledge Layer
