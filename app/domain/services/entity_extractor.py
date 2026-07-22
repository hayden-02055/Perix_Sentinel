"""Entity extraction v2 (SDD Perix_Sentinel_Clusterer_Impl_SDD_A2a_A3 §5).

Pure functions, no I/O. Replaces the v0.1 regex-only model extraction — A0
measured 30% false positives from `_MODEL_RE` (e.g. "February 2026",
"Scholars 2020", "AutoScout 24") because dates and arbitrary capitalized
words matched the same pattern as real model names. Org names and model
families are both closed sets in this domain, so both are matched against
whitelists instead.
"""
from __future__ import annotations

import re

_ORG_ALIASES: dict[str, set[str]] = {
    "openai":      {"openai"},
    "anthropic":   {"anthropic", "claude"},
    "google":      {"google", "deepmind", "google deepmind", "gemini"},
    "meta":        {"meta", "meta ai", "facebook"},
    "mistral":     {"mistral", "mistral ai"},
    "nvidia":      {"nvidia"},
    "huggingface": {"huggingface", "hugging face"},
    "deepseek":    {"deepseek"},
    "alibaba":     {"alibaba", "qwen"},
    "moonshot":    {"moonshot", "kimi"},
    "zhipu":       {"zhipu", "glm", "zai-org", "zai"},
    "microsoft":   {"microsoft", "phi"},
    "xai":         {"xai", "grok"},
    "cohere":      {"cohere", "command"},
}

_MODEL_FAMILIES: set[str] = {
    "gpt", "claude", "llama", "gemini", "qwen", "mistral", "mixtral",
    "codestral", "deepseek", "kimi", "glm", "cosmos", "nemotron",
    "phi", "grok", "command", "minicpm", "gemma", "falcon", "yi",
}

_VERSION_RE = re.compile(r"^(\d+(?:\.\d+)*)")
_SEP_RE = re.compile(r"[-_/',]")


def tokenize(text: str) -> list[str]:
    """Lowercase *text* and split on hyphen/underscore/slash/apostrophe/comma + whitespace.

    Apostrophes are treated as separators (not stripped) so possessive
    headlines like "OpenAI's GPT-5.5" still yield a clean "openai" token
    for org-alias matching. Commas are separators too — otherwise a
    trailing comma (e.g. "Science," in "Claude Science, an AI workbench...")
    keeps a word from matching its comma-free form elsewhere, which
    understates title Jaccard similarity (found in origin-origin A0
    observation, docs/notes/clusterer-origin-origin-a0-observation.md).
    """
    normalized = _SEP_RE.sub(" ", text.lower())
    return normalized.split()


def _build_org_alias_index() -> dict[tuple[str, ...], str]:
    index: dict[tuple[str, ...], str] = {}
    for canonical, aliases in _ORG_ALIASES.items():
        for alias in aliases:
            index[tuple(tokenize(alias))] = canonical
    return index


_ORG_ALIAS_TOKENS = _build_org_alias_index()


def _extract_orgs(tokens: list[str]) -> set[str]:
    orgs: set[str] = set()
    n = len(tokens)
    for i in range(n):
        for window in (1, 2):
            if i + window > n:
                continue
            canonical = _ORG_ALIAS_TOKENS.get(tuple(tokens[i : i + window]))
            if canonical:
                orgs.add(canonical)
    return orgs


def _extract_models(tokens: list[str]) -> set[tuple[str, str]]:
    models: set[tuple[str, str]] = set()
    n = len(tokens)
    for i, token in enumerate(tokens):
        for family in _MODEL_FAMILIES:
            version: str | None = None
            if token == family:
                if i + 1 < n:
                    match = _VERSION_RE.match(tokens[i + 1])
                    version = match.group(1) if match else ""
                else:
                    version = ""
            elif token.startswith(family):
                match = _VERSION_RE.match(token[len(family):])
                if match:
                    version = match.group(1)
            if version is not None:
                models.add((family, version))
    return models


def extract_entities(title: str) -> dict:
    """Extract {"org": set[str], "model": set[tuple[str, str]]} from *title*.

    Matching input is intentionally limited to the title (SDD v0.1 §2.6) to
    avoid boilerplate summary text polluting the entity sets.
    """
    tokens = tokenize(title)
    return {
        "org": _extract_orgs(tokens),
        "model": _extract_models(tokens),
    }
