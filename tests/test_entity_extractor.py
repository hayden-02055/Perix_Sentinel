"""Entity extractor v2 tests (SDD A2a-P1).

test_extract_rejects_a0_false_positives pins the exact 3 false positives
A0 measured against the v0.1 regex approach — this whitelist design must
structurally exclude them without any date-pattern guard.
"""
from __future__ import annotations

from app.domain.services.entity_extractor import extract_entities


def test_extract_org():
    assert extract_entities("OpenAI announces GPT-5.5")["org"] == {"openai"}
    assert extract_entities("Google DeepMind ships new model")["org"] == {"google"}
    assert extract_entities("zai-org/GLM-5.2")["org"] == {"zhipu"}
    assert extract_entities("Meta AI open-sources Llama 4")["org"] == {"meta"}
    assert extract_entities("Some unrelated headline")["org"] == set()


def test_extract_model_variants():
    assert extract_entities("OpenAI announces GPT-5.5")["model"] == {("gpt", "5.5")}
    assert extract_entities("Qwen3.6 GGUF derivative")["model"] == {("qwen", "3.6")}
    assert extract_entities("Meta ships Llama 4")["model"] == {("llama", "4")}
    assert extract_entities("NVIDIA Cosmos launches")["model"] == {("cosmos", "")}


def test_extract_rejects_a0_false_positives():
    assert extract_entities("Disrupting malicious uses of AI | February 2026")["model"] == set()
    assert extract_entities("OpenAI Scholars 2020: Final projects")["model"] == set()
    assert extract_entities("AutoScout24 scales engineering with AI-powered workflows")["model"] == set()
