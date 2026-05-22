import httpx

from app.core.config import settings
from app.core.logger import get_logger
from app.domain.models.collected_item import CollectedItem
from app.domain.ports.publisher import PublisherPort
from app.domain.services.briefing_generator import generate_briefing

logger = get_logger(__name__)


class DiscordPublisher(PublisherPort):
    def __init__(self, webhook_url: str | None = None) -> None:
        self._webhook_url = webhook_url or settings.discord_webhook_url

    async def publish(self, items: list[CollectedItem]) -> None:
        if not items:
            return
        if not self._webhook_url:
            raise RuntimeError(
                "DISCORD_WEBHOOK_URL is not configured — cannot publish briefings"
            )

        async with httpx.AsyncClient(timeout=10.0) as client:
            for item in items:
                content = generate_briefing(item)
                response = await client.post(
                    self._webhook_url,
                    json={"content": content},
                )
                if response.status_code >= 300:
                    logger.error(
                        "Discord webhook failed: status=%s body=%s",
                        response.status_code,
                        response.text[:500],
                    )
                    response.raise_for_status()
                logger.info("Briefing published: %s (score=%d)", item.title, item.score)
