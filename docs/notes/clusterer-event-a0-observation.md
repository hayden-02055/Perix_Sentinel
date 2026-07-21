# Clusterer + Event 모델 SDD — A0 관측 기록

작성일: 2026-07-21

## 1. Ground truth 존재 여부 (가장 중요) — 실측 결과: 0쌍, 구조적 원인 확인

### 1차 확인 (기존 DB 스냅샷)

`2026-07-10` 이후 published된 origin 항목이 0건. Origin 소스(OpenAI/Anthropic/DeepMind/
Google Research/NVIDIA 등)는 대부분 `2026-06-30` 이전 백필 데이터에서 멈춰 있고, coverage
(TechCrunch/MarkTechPost)는 `2026-07-17~07-21`이라 시간창이 전혀 겹치지 않았다.

### 2차 확인 (origin `/collect` 라이브 실행 후)

사용자 승인 하에 `POST /collect`(Tier1, `DiscordPublisher` 배선)를 라이브 실행해 origin
소스의 최신 데이터를 확보했다. 부수효과로 실제 Discord 채널에 38건이 브리핑 발행됨
(openai 7, arxiv 6, huggingface 6, github 18, nvidia 1) — 참고로 기록.

이후 origin 데이터가 coverage와 시간대상 겹치게 됐음에도, SDD §2.3의 게이트를 그대로
적용해 교차 매칭한 결과 **여전히 확정 매칭 0쌍**이었다. 개체명(조직)이 겹치는 후보는
5쌍 나왔으나 전부 모델 교집합 0 + 후보 2개 이상이라 게이트2(§2.3)를 통과하지 못했고,
내용을 사람이 직접 확인해도 실제로는 다른 사건이었다:

| coverage | org-겹침 origin 후보 | 실제 동일 사건인가 |
|---|---|---|
| TechCrunch "Anthropic's $1.5B copyright settlement" (07-21) | Anthropic "AI for Science grants" (07-20) | 아니오 — 무관한 주제 |
| MarkTechPost "NVIDIA srt-slurm 튜토리얼" (07-21) | NVIDIA GTC 키노트 포스트 3건(Rubin/Vera/GB300, 07-21) | 아니오 |
| MarkTechPost "NVIDIA Cosmos 3 Edge 출시" (07-21) | NVIDIA "Post-Train Cosmos 3 in One Day"(07-14) | 유사 모델군이나 별개 이벤트. 시차 +159h로 §2.3의 +48h 창도 벗어남 |
| MarkTechPost "Alibaba Qwen-Audio-3.0-TTS" (07-20) | HuggingFace "Qwen3.6 GGUF 파생"(07-20) | 아니오 — 제3자 파인튜닝 vs 공식 발표 |
| MarkTechPost "MiniCPM5-1B on Claude Fable 5" (07-20) | Anthropic "AI for Science grants"(07-20) | 아니오 |

### 근본 원인 (데이터 축적만으로는 해결 안 됨)

1. **origin 컬렉터 세트가 coverage가 다루는 조직을 다 커버하지 못한다.** `_ORG_ALIASES`에는
   Alibaba/Moonshot/DeepSeek/Zhipu가 있지만 Tier1 origin 컬렉터에는 해당 조직의 공식
   블로그가 없다(OpenAI/Anthropic/DeepMind/Meta/Mistral/HuggingFace/NVIDIA/Google Research/
   arXiv/GitHub Trending/HackerNews뿐).
2. **커버되는 조직도 조직명만 겹치면 실제로는 다른 사건일 확률이 높다** — SDD §2.1이 이미
   예견한 "OpenAI는 하루에도 여러 사건" 문제가 실측에서 그대로 재현됨.

### 결론 및 결정

**A2(clusterer.py 순수 로직 구현 + 골든 테스트)는 보류한다.** 실제 사건 쌍이 없는 상태에서
골든 fixture를 만들면 가공 데이터가 되어 이 프로젝트가 지켜온 "실데이터 기반 골든 테스트"
원칙과 어긋난다. 대신 **A1(Event/EventMember 모델, EventRepositoryPort, SQLite 어댑터,
스키마)만 먼저 진행**한다 — ground truth와 무관한 순수 구조 작업이기 때문이다.

재개 조건: 아래 중 하나가 갖춰지면 A2 재개.
- origin 컬렉터가 Alibaba/Moonshot 등으로 확장되어 실제 매칭 가능한 조직 커버리지가 넓어지거나
- 기존 origin 소스(OpenAI/Anthropic/NVIDIA 등)에서 게이트2(조직+모델 교집합 또는 유일 후보)를
  실제로 통과하는 사건 쌍이 자연 발생적으로 관측되거나

## 2. 개체 추출 정밀도 — 부분 확인, 위험 신호 확인됨

실제 제목 100건 샘플(`collected_items` 랜덤 샘플)에 §2.2 정규식/사전을 그대로 적용:

- 조직 매칭(`_ORG_ALIASES`): 22/100 히트 — 합리적인 재현율.
- 모델 정규식(`_MODEL_RE = r"\b([A-Z][A-Za-z]{1,15})[-\s]?(\d+(?:\.\d+)?)\b"`): 10건 매칭
  중 최소 3건이 명백한 오탐:
  - `"Disrupting malicious uses of AI | February 2026"` → `("February", "2026")`
  - `"OpenAI Scholars 2020: Final projects"` → `("Scholars", "2020")`
  - `"AutoScout24 scales engineering with AI-powered workflows"` → `("AutoScout", "24")`

SDD 본문이 직접 경고한 "Q4 2026류 오탐"이 실제로 재현됐다. **결정**: A2 착수 시 모델
정규식에 날짜 패턴(월 이름 + 연도, "Q숫자" 등) 제외 가드를 추가하거나, 사전 기반 화이트
리스트 방식으로 보강이 필요하다 (이번 세션 범위 아님, A2 착수 시 처리).

## 3. 시간창 타당성 — 측정 불가 (1번에 의존)

확정 매칭 쌍이 0개라 실제 시차 분포를 측정할 수 없었다. 다만 근접 사례("NVIDIA Cosmos 3"
계열)의 격차가 +159h로 관측되어, 실제 매칭이 발생하기 시작하면 +48h 창이 일부 사례에서
타이트할 수 있음을 참고 신호로 남긴다 (확정 아님, 재측정 필요).

## 4. 배포 형태 — 확인 완료

`Dockerfile` + `docker-compose.yml` 모두 단일 컨테이너(`sentinel` 서비스 1개, uvicorn
프로세스 1개, `perix_sentinel.db`를 볼륨 마운트). **결정**: 스케줄러는 APScheduler
(인프로세스)로 간다. 외부 cron/별도 프로세스 불필요.

## A1 진행 결과 (같은 세션)

Ground truth 부재로 A2는 보류하되, A1(구조 작업)은 완료:

- `app/domain/models/event.py` — `Event`, `EventMember` (SDD §5.1 그대로)
- `app/domain/ports/event_repository.py` — `EventRepositoryPort` (`upsert`/`get_by_id`/`mark_briefed`)
- `app/infrastructure/repositories/sqlite_event_repository.py` — SQLite 어댑터, `events` 테이블
  + 인덱스 2개(§5.2 스키마 그대로), `event_id` 기준 `ON CONFLICT DO UPDATE` upsert로 멱등성 확보
- `app/main.py` lifespan에 `SqliteEventRepository().init_db()` 추가 — 기존 `SqliteItemRepository`
  초기화와 동일한 패턴. 실제 `perix_sentinel.db`에 `events` 테이블 생성 확인됨(라이브 기동 검증).
- `tests/test_event_repository.py` — round-trip, upsert 멱등성, mark_briefed, 존재하지 않는
  id 조회 4종. 클러스터링 로직은 다루지 않음(A2 범위).
- 전체 테스트: 66 passed (기존 62 + 신규 4).

### A1 리뷰 후속 조치 (커밋 전 반영 필요)

구조 테스트는 통과했지만, Event 저장소의 중복 브리핑 방지 계약 관점에서 아래 2개는
수정이 필요하다.

1. **`upsert()`가 `is_briefed`/`briefed_at`을 되돌릴 수 있음**
   - 위치: `app/infrastructure/repositories/sqlite_event_repository.py`
   - 현재 `ON CONFLICT(event_id) DO UPDATE`가 `is_briefed=excluded.is_briefed`,
     `briefed_at=excluded.briefed_at`까지 덮어쓴다.
   - A2에서 같은 `event_id`를 재클러스터링하면 새 `Event` 기본값은 `is_briefed=False`라,
     이미 브리핑된 Event가 다시 미브리핑 상태로 돌아갈 수 있다.
   - SDD §7.2는 Event 쪽 `is_briefed`를 중복 발행 방지 신호로 쓰기로 했으므로, update 시
     기존 `events.is_briefed`/`events.briefed_at`을 보존하거나 단조 증가만 허용해야 한다.
   - 회귀 테스트: `mark_briefed()` 후 같은 `event_id`로 `upsert()`해도 `is_briefed=True`와
     `briefed_at`이 유지되는 케이스를 추가한다.

2. **빈 `event_id`가 그대로 upsert될 수 있음**
   - 위치: `app/domain/models/event.py`, `app/infrastructure/repositories/sqlite_event_repository.py`
   - `Event.event_id` 기본값이 `""`이고 repository가 이를 거부하지 않는다.
   - 클러스터러가 `md5(origin.url_hash)` 생성을 빠뜨리면 모든 Event가 `event_id=""` 하나로
     충돌해 서로 덮어쓴다.
   - `SqliteEventRepository.upsert()`에서 빈 `event_id`를 `ValueError`로 거부하거나, Event 생성
     helper에서 `event_id` 생성을 강제해야 한다.
   - 회귀 테스트: 빈 `event_id` Event를 `upsert()`하면 실패하는 케이스를 추가한다.

**A2(clusterer.py, `get_unbriefed_since`, `DailyBriefingUseCase`, 엔드포인트, 스케줄러)는
위 "재개 조건"이 충족될 때까지 보류.**
