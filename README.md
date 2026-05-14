# Perix Sentinel

> Observe the signals before the world notices them.

Perix Sentinel is an AI intelligence sentinel designed to collect, filter, summarize, and deliver meaningful signals from the rapidly evolving AI ecosystem.

This project is not just an AI news scraper.  
It aims to become a personal intelligence layer for tracking AI research, open-source trends, model releases, and community movements.

---

## Why Perix Sentinel Exists

The AI ecosystem moves too fast for a single person to continuously track.

Every day, new papers, models, datasets, frameworks, technical blogs, and community discussions appear across the web.

Most of them are noise.  
Some of them are signals.

Perix Sentinel exists to detect those meaningful signals early and deliver them in a clear, compact, and useful form.

---

## Core Philosophy

- Signal over noise
- Evidence over hype
- Automation over repetition
- Clarity over volume
- Human-centric intelligence

---

## Signal Sources

Perix Sentinel will collect signals from multiple layers of the AI ecosystem.

| Layer | Sources | Purpose |
|---|---|---|
| Trend Signal | GitHub, Hacker News | Detect rising open-source projects and developer trends |
| AI Lab Signal | OpenAI, Anthropic, Google DeepMind, Meta AI | Track base model releases and major AI lab updates |
| Research Signal | arXiv, Papers with Code | Monitor papers, research directions, and technical breakthroughs |
| Model & Dataset Signal | Hugging Face | Track model releases, datasets, and community usage |
| Community Signal | Reddit, blogs, newsletters | Understand memes, discussions, and early adoption signals |

---

## MVP Architecture

```text
RSS / API / Crawling
        ↓
Collector Layer
        ↓
Deduplication & Filtering
        ↓
Signal Ranking
        ↓
LLM Summary
        ↓
Telegram Morning Briefing

Initial MVP Goals
Collect AI-related updates through RSS and public APIs
Store collected items in a database
Remove duplicates
Summarize key items using an LLM
Send a daily AI briefing through Telegram
Monitor the system with Aegis Sentinel in the future
Long-Term Vision

Perix Sentinel aims to evolve into a personal AI research assistant.

Future directions include:

Signal Ranking System
Knowledge Graph
RAG-based AI Memory
Personalized AI Trend Intelligence
Autonomous Research Assistant
Sentinel Ecosystem

Perix Sentinel is part of the broader Sentinel ecosystem.

Project	Role
Perix Sentinel	AI Intelligence & Signal Observation
Triton Sentinel	AI Model Training & Fine-tuning
Aegis Sentinel	Infrastructure Monitoring & Recovery

Together, they form a personal AI research and engineering ecosystem.

Current Status

This project is in the early planning and MVP design stage.

The first implementation target is a simple RSS/API-based AI trend collector with Telegram briefing support.

License

TBD