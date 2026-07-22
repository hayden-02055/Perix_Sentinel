"""Clusterer tests (SDD Perix_Sentinel_Clusterer_Impl_SDD_A2a_A3 §9, P2).

test_clusterer_a0_negative_pairs reconstructs the 5 real (title, org,
timing) shapes from docs/notes/clusterer-event-a0-observation.md that a
human confirmed were NOT the same event, each padded with a same-org
distractor origin so candidate_count >= 2 exactly as A0 observed
("전부 모델 교집합 0 + 후보 2개 이상") — with count == 1 the gate2 unique-
candidate bonus would let these through on org overlap alone.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models.collected_item import CollectedItem
from app.domain.services.clusterer import FuzzyClusterer

# Fuzzy logic is isolated into FuzzyClusterer (Passthrough Clusterer SDD §6);
# these legacy gate tests exercise it unchanged via the class method.
cluster = FuzzyClusterer().cluster


def _item(source: str, title: str, published_at: datetime, url: str) -> CollectedItem:
    return CollectedItem(source=source, title=title, url=url, published_at=published_at)


def _dt(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)


def test_clusterer_a0_negative_pairs():
    items = [
        # Row 1: org overlaps (anthropic), no model mention either side, 2 anthropic candidates.
        _item("Anthropic", "Anthropic announces AI for Science grants", _dt(7, 20, 10), "https://anthropic.com/1"),
        _item("Anthropic", "Anthropic hires new safety researchers", _dt(7, 20, 12), "https://anthropic.com/2"),
        _item(
            "TechCrunch",
            "Anthropic's $1.5B copyright settlement with authors",
            _dt(7, 21, 9),
            "https://techcrunch.com/1",
        ),
        # Row 2: org overlaps (nvidia), 3 keynote candidates, no model family in any title.
        _item("NVIDIA", "GTC keynote: Rubin platform unveiled", _dt(7, 21, 8), "https://nvidia.com/1"),
        _item("NVIDIA", "GTC keynote: Vera CPU details revealed", _dt(7, 21, 8, 30), "https://nvidia.com/2"),
        _item("NVIDIA", "GTC keynote: GB300 systems shipping", _dt(7, 21, 9), "https://nvidia.com/3"),
        _item(
            "MarkTechPost",
            "NVIDIA srt-slurm tutorial for multi-node training",
            _dt(7, 21, 18),
            "https://marktechpost.com/1",
        ),
        # Row 3: model family matches (cosmos) but time window fails (+159h).
        _item("NVIDIA", "Post-Train Cosmos 3 in One Day", _dt(7, 14, 18), "https://nvidia.com/4"),
        _item(
            "MarkTechPost",
            "NVIDIA Cosmos 3 Edge launches",
            _dt(7, 21, 9),
            "https://marktechpost.com/2",
        ),
        # Row 4: HF origin's model_id fuses the version onto "qwen", so the bare "qwen"
        # org alias never appears as its own token — org set stays empty.
        _item("HuggingFace", "bartowski/Qwen3.6-GGUF", _dt(7, 20, 10), "https://huggingface.co/1"),
        _item("HuggingFace", "TheBloke/DeepSeek-V4-GGUF", _dt(7, 20, 11), "https://huggingface.co/2"),
        _item(
            "MarkTechPost",
            "Alibaba launches Qwen-Audio-3.0-TTS",
            _dt(7, 20, 15),
            "https://marktechpost.com/3",
        ),
        # Row 5: org overlaps (anthropic, via "Claude" mention) but reuses the same
        # 2 anthropic candidates from row 1 — model mismatch still rejects it.
        _item(
            "MarkTechPost",
            "MiniCPM5-1B benchmarks beat Claude Fable 5",
            _dt(7, 20, 20),
            "https://marktechpost.com/4",
        ),
    ]

    events = cluster(items)

    coverage_titles = {
        "Anthropic's $1.5B copyright settlement with authors",
        "NVIDIA srt-slurm tutorial for multi-node training",
        "NVIDIA Cosmos 3 Edge launches",
        "Alibaba launches Qwen-Audio-3.0-TTS",
        "MiniCPM5-1B benchmarks beat Claude Fable 5",
    }
    for event in events:
        echo_titles = {m.title for m in event.members if m.role == "echo"}
        assert not (echo_titles & coverage_titles)
        assert event.echo_count == 0

    assert len(events) == 8  # every origin gets its own Event, none merged


def test_clusterer_time_window():
    origin = _item("OpenAI", "OpenAI ships GPT-5.5 agents", _dt(7, 20, 0), "https://openai.com/1")

    too_late = _item("TechCrunch", "OpenAI's GPT-5.5 agents go live", _dt(7, 22, 1), "https://techcrunch.com/late")
    too_early = _item("TechCrunch", "OpenAI's GPT-5.5 agents leak early", _dt(7, 19, 16, 59), "https://techcrunch.com/early")
    in_window_late = _item("TechCrunch", "OpenAI's GPT-5.5 agents go live", _dt(7, 21, 23), "https://techcrunch.com/inwindow-late")
    in_window_early = _item("TechCrunch", "OpenAI's GPT-5.5 agents leak early", _dt(7, 19, 19), "https://techcrunch.com/inwindow-early")

    rejected = cluster([origin, too_late, too_early])
    assert rejected[0].echo_count == 0

    accepted = cluster([origin, in_window_late, in_window_early])
    assert accepted[0].echo_count == 2


def test_clusterer_entity_gate():
    origin_a = _item("Anthropic", "Anthropic ships Claude 5 update", _dt(7, 20, 10), "https://anthropic.com/1")
    origin_b = _item("Anthropic", "Anthropic hires new safety researchers", _dt(7, 20, 12), "https://anthropic.com/2")
    coverage = _item(
        "TechCrunch", "Anthropic faces new copyright lawsuit", _dt(7, 21, 9), "https://techcrunch.com/1"
    )

    events = cluster([origin_a, origin_b, coverage])
    assert all(e.echo_count == 0 for e in events)


def test_clusterer_unique_candidate_is_per_org_not_per_window():
    """Gate2's unique-candidate bonus must count same-org candidates, not every
    origin sharing the time window (code review finding #1 on the initial
    clusterer implementation) — an unrelated NVIDIA post in-window must not
    force the OpenAI candidate to need a model match it has no reason to have.
    """
    origin_openai = _item("OpenAI", "OpenAI ships enterprise updates", _dt(7, 21, 9), "https://openai.com/1")
    origin_nvidia = _item("NVIDIA", "NVIDIA ships enterprise updates", _dt(7, 21, 9, 30), "https://nvidia.com/1")
    coverage = _item(
        "TechCrunch", "OpenAI expands enterprise access", _dt(7, 21, 14), "https://techcrunch.com/1"
    )

    events = cluster([origin_openai, origin_nvidia, coverage])

    openai_event = next(e for e in events if e.members[0].url == "https://openai.com/1")
    nvidia_event = next(e for e in events if e.members[0].url == "https://nvidia.com/1")
    assert openai_event.echo_count == 1
    assert nvidia_event.echo_count == 0


def test_clusterer_tiebreak():
    coverage = _item(
        "TechCrunch", "OpenAI launches GPT-5.5 with agentic tooling", _dt(7, 21, 14), "https://techcrunch.com/1"
    )
    close_match = _item(
        "OpenAI", "OpenAI introduces GPT-5.5 agentic tooling", _dt(7, 21, 9), "https://openai.com/close"
    )
    far_match = _item(
        "OpenAI", "OpenAI ships GPT-5.5 pricing update", _dt(7, 21, 9), "https://openai.com/far"
    )

    events = cluster([close_match, far_match, coverage])
    winner = next(e for e in events if e.echo_count == 1)
    assert winner.members[0].url == "https://openai.com/close"
    loser = next(e for e in events if e.echo_count == 0)
    assert loser.members[0].url == "https://openai.com/far"


def test_clusterer_hf_skips_gate3():
    coverage = _item(
        "TechCrunch", "GLM 5.2 released with strong benchmarks", _dt(7, 20, 15), "https://techcrunch.com/1"
    )
    hf_origin = _item("HuggingFace", "zai-org/GLM-5.2", _dt(7, 20, 10), "https://huggingface.co/1")
    official_origin = _item("Zhipu", "Zhipu ships GLM 5.2", _dt(7, 20, 11), "https://zhipu.ai/1")

    events = cluster([hf_origin, official_origin, coverage])

    official_event = next(e for e in events if e.members[0].url == "https://zhipu.ai/1")
    hf_event = next(e for e in events if e.members[0].url == "https://huggingface.co/1")
    assert official_event.echo_count == 1
    assert hf_event.echo_count == 0


def test_clusterer_single_assignment():
    coverage = _item(
        "TechCrunch", "OpenAI launches GPT-5.5 with agentic tooling", _dt(7, 21, 14), "https://techcrunch.com/1"
    )
    origin_a = _item("OpenAI", "OpenAI introduces GPT-5.5 agentic tooling", _dt(7, 21, 9), "https://openai.com/a")
    origin_b = _item("OpenAI", "OpenAI ships GPT-5.5 agentic tooling now", _dt(7, 21, 10), "https://openai.com/b")

    events = cluster([origin_a, origin_b, coverage])

    total_echo = sum(e.echo_count for e in events)
    assert total_echo == 1  # attached to exactly one Event, never both


def test_event_id_idempotent():
    origin = _item("OpenAI", "OpenAI ships GPT-5.5 agents", _dt(7, 20, 0), "https://openai.com/1")

    first_run = cluster([origin])
    second_run = cluster([origin])

    assert first_run[0].event_id == second_run[0].event_id
    assert first_run[0].event_id != ""
