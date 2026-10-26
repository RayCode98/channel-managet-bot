import uuid
from datetime import UTC, datetime

import pytest

from channel_manager_bot.handlers.templates import sync_recurrent_publications
from channel_manager_bot.models import (
    ContentTemplate,
    Publication,
    PublicationButton,
    PublicationStatus,
    TemplateButton,
)


class ScalarSession:
    def __init__(self, publications):
        self.publications = publications

    async def scalars(self, _statement):
        return self.publications


@pytest.mark.asyncio
async def test_template_changes_replace_only_the_future_recurrence_snapshot():
    workspace_id = uuid.uuid4()
    template_id = uuid.uuid4()
    template = ContentTemplate(
        id=template_id,
        workspace_id=workspace_id,
        creator_user_id=10,
        name="Oferta",
        source_chat_id=100,
        source_message_id=200,
        source_content_type="text",
        source_text_html="<b>Nuevo</b>",
        source_text_plain="Nuevo",
        source_entities_json='[{"type":"custom_emoji"}]',
        preview="Nuevo",
        delete_after_minutes=60,
    )
    template.buttons.append(
        TemplateButton(
            id=uuid.uuid4(),
            template_id=template_id,
            row_index=0,
            position=0,
            text="Comprar",
            url="https://example.com/new",
            style="success",
        )
    )
    publication = Publication(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        template_id=template_id,
        creator_user_id=10,
        source_chat_id=1,
        source_message_id=2,
        source_content_type="text",
        source_text_html="Anterior",
        source_text_plain="Anterior",
        preview="Anterior",
        status=PublicationStatus.scheduled,
        scheduled_at=datetime(2026, 10, 28, 12, tzinfo=UTC),
        recurrence_interval_days=1,
        delete_after_minutes=None,
    )
    publication.buttons.append(
        PublicationButton(
            id=uuid.uuid4(),
            publication_id=publication.id,
            row_index=0,
            position=0,
            text="Anterior",
            url="https://example.com/old",
            style="danger",
        )
    )

    count = await sync_recurrent_publications(ScalarSession([publication]), template)

    assert count == 1
    assert publication.source_chat_id == 100
    assert publication.source_message_id == 200
    assert publication.source_text_html == "<b>Nuevo</b>"
    assert publication.source_text_plain == "Nuevo"
    assert publication.source_entities_json == '[{"type":"custom_emoji"}]'
    assert publication.delete_after_minutes == 60
    assert [(button.text, button.url, button.style) for button in publication.buttons] == [
        ("Comprar", "https://example.com/new", "success")
    ]
