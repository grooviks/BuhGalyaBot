from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Workspace(Timestamped, Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class Chat(Timestamped, Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255))


class AllowedActor(Timestamped, Base):
    __tablename__ = "allowed_actors"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))


class Person(Timestamped, Base):
    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_people_workspace_name"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)
    telegram_username: Mapped[str | None] = mapped_column(String(32))


class SoftDeletable:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_telegram_user_id: Mapped[int | None] = mapped_column(BigInteger)


class Debt(SoftDeletable, Timestamped, Base):
    __tablename__ = "debts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    person_id: Mapped[UUID] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    amount_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class DebtRepayment(SoftDeletable, Timestamped, Base):
    __tablename__ = "debt_repayments"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    debt_id: Mapped[UUID] = mapped_column(ForeignKey("debts.id"), nullable=False, index=True)
    amount_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class Collection(Timestamped, Base):
    __tablename__ = "collections"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    default_target_rub: Mapped[int | None] = mapped_column(Integer)
    created_by_telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class CollectionRound(Timestamped, Base):
    __tablename__ = "collection_rounds"
    __table_args__ = (
        UniqueConstraint("collection_id", "period_key", name="uq_round_collection_period"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("collections.id"), nullable=False, index=True
    )
    period_key: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")


class CollectionParticipant(Timestamped, Base):
    __tablename__ = "collection_participants"
    __table_args__ = (UniqueConstraint("round_id", "person_id", name="uq_round_participant"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    round_id: Mapped[UUID] = mapped_column(
        ForeignKey("collection_rounds.id"), nullable=False, index=True
    )
    person_id: Mapped[UUID] = mapped_column(ForeignKey("people.id"), nullable=False, index=True)
    target_rub: Mapped[int | None] = mapped_column(Integer)


class CollectionPayment(SoftDeletable, Timestamped, Base):
    __tablename__ = "collection_payments"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(
        ForeignKey("collection_participants.id"), nullable=False, index=True
    )
    amount_rub: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
