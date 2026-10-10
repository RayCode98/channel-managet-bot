from dataclasses import dataclass

from sqlalchemy import select

from ..database import SessionFactory
from ..models import CampaignClick, CampaignLink
from ..repository import utcnow


@dataclass(frozen=True)
class CampaignClickResult:
    name: str
    target_url: str


async def record_campaign_click(token: str, user_id: int) -> CampaignClickResult | None:
    """Record a bot deep-link visit and return its destination if active."""
    async with SessionFactory() as session:
        link = await session.scalar(
            select(CampaignLink).where(CampaignLink.token == token, CampaignLink.enabled.is_(True))
        )
        if link is None:
            return None
        session.add(
            CampaignClick(
                campaign_link_token=link.token,
                user_id=user_id,
                clicked_at=utcnow(),
            )
        )
        await session.commit()
        return CampaignClickResult(name=link.name, target_url=link.target_url)
