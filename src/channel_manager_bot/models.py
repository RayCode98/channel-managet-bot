import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    editor = "editor"


class ChannelStatus(str, enum.Enum):
    active = "active"
    missing_permissions = "missing_permissions"
    removed = "removed"


class PublicationStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    publishing = "publishing"
    published = "published"
    partial = "partial"
    failed = "failed"
    cancelled = "cancelled"


class User(Base):
    __tablename__ = "users"
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"))
    timezone: Mapped[str] = mapped_column(String(64), default="America/Mexico_City")
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    welcome_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    welcome_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id", ondelete="CASCADE"))
    role: Mapped[Role] = mapped_column(Enum(Role, name="role_enum"), default=Role.editor)


class Channel(Base):
    __tablename__ = "channels"
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[ChannelStatus] = mapped_column(
        Enum(ChannelStatus, name="channel_status_enum"), default=ChannelStatus.active
    )
    can_post_messages: Mapped[bool] = mapped_column(Boolean, default=False)
    member_count: Mapped[int | None] = mapped_column(Integer)
    previous_member_count: Mapped[int | None] = mapped_column(Integer)
    welcome_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    welcome_source_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    welcome_source_message_id: Mapped[int | None] = mapped_column(BigInteger)
    welcome_content_type: Mapped[str | None] = mapped_column(String(20))
    welcome_text_template: Mapped[str | None] = mapped_column(Text)
    welcome_file_id: Mapped[str | None] = mapped_column(String(512))
    welcome_button_text: Mapped[str | None] = mapped_column(String(64))
    welcome_button_url: Mapped[str | None] = mapped_column(String(2048))
    farewell_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    farewell_source_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    farewell_source_message_id: Mapped[int | None] = mapped_column(BigInteger)
    farewell_content_type: Mapped[str | None] = mapped_column(String(20))
    farewell_text_template: Mapped[str | None] = mapped_column(Text)
    farewell_file_id: Mapped[str | None] = mapped_column(String(512))
    added_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    welcome_buttons: Mapped[list["WelcomeButton"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )
    farewell_buttons: Mapped[list["FarewellButton"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class WelcomeButton(Base):
    __tablename__ = "welcome_buttons"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.telegram_chat_id", ondelete="CASCADE"), index=True
    )
    row_index: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(String(2048))
    style: Mapped[str | None] = mapped_column(String(16))


class FarewellButton(Base):
    __tablename__ = "farewell_buttons"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.telegram_chat_id", ondelete="CASCADE"), index=True
    )
    row_index: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(String(2048))
    style: Mapped[str | None] = mapped_column(String(16))


class Publication(Base):
    __tablename__ = "publications"
    __table_args__ = (
        UniqueConstraint(
            "recurrence_series_id",
            "recurrence_sequence",
            name="uq_publications_recurrence_series_sequence",
        ),
        CheckConstraint(
            "recurrence_interval_days BETWEEN 1 AND 365",
            name="ck_publications_recurrence_interval_days",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    creator_user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"))
    source_chat_id: Mapped[int] = mapped_column(BigInteger)
    source_message_id: Mapped[int] = mapped_column(BigInteger)
    preview: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[PublicationStatus] = mapped_column(
        Enum(PublicationStatus, name="publication_status_enum"),
        default=PublicationStatus.draft,
        index=True,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delete_after_minutes: Mapped[int | None] = mapped_column(Integer)
    recurrence_series_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    recurrence_interval_days: Mapped[int | None] = mapped_column(Integer)
    recurrence_sequence: Mapped[int | None] = mapped_column(Integer)
    recurrence_timezone: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    buttons: Mapped[list["PublicationButton"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class PublicationButton(Base):
    __tablename__ = "publication_buttons"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), index=True
    )
    row_index: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(String(2048))


class PublicationChannel(Base):
    __tablename__ = "publication_channels"
    __table_args__ = (UniqueConstraint("publication_id", "channel_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), index=True
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.telegram_chat_id", ondelete="CASCADE")
    )


class PublishedMessage(Base):
    __tablename__ = "published_messages"
    __table_args__ = (UniqueConstraint("publication_id", "channel_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("publications.id", ondelete="CASCADE"), index=True
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.telegram_chat_id", ondelete="CASCADE")
    )
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    delete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delete_attempts: Mapped[int] = mapped_column(Integer, default=0)
    delete_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContentTemplate(Base):
    __tablename__ = "content_templates"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    creator_user_id: Mapped[int] = mapped_column(ForeignKey("users.telegram_id"))
    name: Mapped[str] = mapped_column(String(100))
    source_chat_id: Mapped[int] = mapped_column(BigInteger)
    source_message_id: Mapped[int] = mapped_column(BigInteger)
    preview: Mapped[str | None] = mapped_column(String(500))
    delete_after_minutes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    buttons: Mapped[list["TemplateButton"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class TemplateButton(Base):
    __tablename__ = "template_buttons"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_templates.id", ondelete="CASCADE"), index=True
    )
    row_index: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(String(2048))


class JoinRequestEvent(Base):
    __tablename__ = "join_request_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.telegram_chat_id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger)
    invite_link: Mapped[str | None] = mapped_column(String(2048))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
