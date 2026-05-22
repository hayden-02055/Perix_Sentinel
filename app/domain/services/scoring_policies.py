SOURCE_WEIGHTS: dict[str, int] = {
    "OpenAI": 10,
    "Anthropic": 9,
    "DeepMind": 9,
    "Meta AI": 8,
    "Mistral AI": 8,
    "HuggingFace": 7,
    "GitHub Trending": 7,
}

KEYWORD_WEIGHTS: dict[str, int] = {
    "agent": 5,
    "mcp": 5,
    "reasoning": 5,
    "multimodal": 4,
    "llama": 4,
    "claude": 4,
    "gpt": 4,
    "gemini": 4,
    "mixtral": 4,
    "moe": 4,
    "rag": 4,
    "memory": 3,
    "inference": 3,
    "fine-tuning": 3,
    "open-weight": 3,
    "safety": 3,
}

BRIEFING_THRESHOLD: int = 15


def classify_importance(score: int) -> str:
    if score >= 25:
        return "critical"
    if score >= 15:
        return "high"
    if score >= 10:
        return "normal"
    return "low"
