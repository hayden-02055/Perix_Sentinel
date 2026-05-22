from app.domain.models.collected_item import CollectedItem


def generate_briefing(item: CollectedItem) -> str:
    lines = [
        "[Perix Sentinel Briefing]",
        "",
        item.title,
        "",
        f"Source: {item.source}",
        f"Score: {item.score} ({item.importance})",
    ]
    if item.reason:
        lines.append(f"Reason: {item.reason}")
    if item.summary:
        summary = item.summary if len(item.summary) <= 300 else item.summary[:297] + "..."
        lines.append(f"Summary: {summary}")
    lines.append(f"URL: {item.url}")
    return "\n".join(lines)
