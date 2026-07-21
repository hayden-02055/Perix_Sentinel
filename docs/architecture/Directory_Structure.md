perix-sentinel/
├── app/
│   ├── main.py                              # FastAPI app + lifespan (init_db x2)
│   ├── core/
│   │   ├── config.py                        # Settings + MATCH_WINDOW_AFTER_H/BEFORE_H constants
│   │   ├── datetime_utils.py                # now_utc/parse_date/from_epoch/parse_struct_time (aware UTC)
│   │   └── logger.py
│   │
│   ├── domain/
│   │   ├── models/
│   │   │   ├── collected_item.py            # CollectedItem (url_hash auto-md5)
│   │   │   └── event.py                     # Event, EventMember
│   │   ├── ports/
│   │   │   ├── collector.py
│   │   │   ├── repository.py                # ItemRepositoryPort
│   │   │   ├── event_repository.py          # EventRepositoryPort
│   │   │   └── publisher.py
│   │   └── services/
│   │       ├── scoring_engine.py            # calculate_score/apply_score
│   │       ├── scoring_policies.py          # SOURCE_WEIGHTS/KEYWORD_WEIGHTS/importance
│   │       ├── entity_extractor.py          # extract_entities — org alias + model family whitelist (pure)
│   │       ├── clusterer.py                 # cluster(items) -> list[Event] — 3-gate matching (pure, no I/O)
│   │       └── briefing_generator.py        # generate_briefing (per-item; Event digest = A3, pending)
│   │
│   ├── application/
│   │   └── use_cases/
│   │       └── collect_trends.py            # CollectTrendsUseCase (still briefs per-item; A3 will strip this)
│   │
│   ├── infrastructure/
│   │   ├── collectors/                      # 1 module per source, source in {} shown
│   │   │   ├── openai_rss_collector.py           {OpenAI}
│   │   │   ├── anthropic_html_collector.py       {Anthropic}
│   │   │   ├── deepmind_html_collector.py        {DeepMind}
│   │   │   ├── meta_html_collector.py            {Meta}
│   │   │   ├── mistral_html_collector.py         {Mistral}
│   │   │   ├── nvidia_rss_collector.py           {NVIDIA}
│   │   │   ├── google_research_rss_collector.py  {Google Research}
│   │   │   ├── huggingface_api_collector.py      {HuggingFace, region-tagged}
│   │   │   ├── github_trending_collector.py      {GitHub Trending}
│   │   │   ├── arxiv_api_collector.py            {arXiv}
│   │   │   ├── hackernews_api_collector.py       {Hacker News, AI-keyword filtered}
│   │   │   ├── techcrunch_rss_collector.py       {TechCrunch}     — Tier2 coverage
│   │   │   └── marktechpost_rss_collector.py     {MarkTechPost}   — Tier2 coverage
│   │   ├── http/
│   │   │   └── async_client.py              # fetch_html/fetch_json, shared retry+backoff
│   │   ├── repositories/
│   │   │   ├── sqlite_item_repository.py
│   │   │   └── sqlite_event_repository.py   # events table, monotonic is_briefed/briefed_at upsert
│   │   └── publishers/
│   │       └── discord_publisher.py
│   │
│   └── interface/
│       └── api/
│           ├── health.py
│           ├── items.py
│           └── collect.py                   # POST /collect (origin, 11 sources) + /collect/coverage (2 sources)
│
├── tests/
│   ├── conftest.py                          # mock_http fixture
│   ├── test_core_datetime_utils.py
│   ├── test_scoring_characterization.py
│   ├── test_event_repository.py             # Event model + SqliteEventRepository (round-trip, upsert monotonicity)
│   ├── test_entity_extractor.py             # org/model whitelist extraction
│   ├── test_clusterer.py                    # 3-gate matching, A0 negative pairs, HF exception, idempotency
│   └── test_<source>_collector_golden.py    # 1 per collector, fixtures/ + *.golden.json pairs
│
├── docs/
│   ├── SDD/                                 # per-feature Software Design Documents
│   ├── architecture/
│   │   └── Directory_Structure.md           # this file
│   └── notes/                               # observation logs (e.g. clusterer A0 ground-truth measurement)
│
├── PROGRESS.md                              # multi-session handoff: done / in-progress / next / open decisions
├── .env / .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml                       # single container, 1 uvicorn process — scheduler will be in-process (APScheduler)
└── README.md
