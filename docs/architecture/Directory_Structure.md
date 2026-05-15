perix-sentinel/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   └── logger.py
│   │
│   ├── domain/
│   │   ├── models/
│   │   │   └── collected_item.py
│   │   └── ports/
│   │       ├── collector.py
│   │       ├── repository.py
│   │       └── publisher.py
│   │
│   ├── application/
│   │   └── use_cases/
│   │       └── collect_trends.py
│   │
│   ├── infrastructure/
│   │   ├── collectors/
│   │   │   └── rss_collector.py
│   │   ├── repositories/
│   │   │   └── sqlite_item_repository.py
│   │   └── publishers/
│   │       └── discord_publisher.py
│   │
│   └── interface/
│       └── api/
│           ├── health.py
│           └── collect.py
│
├── tests/
├── .env
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md

