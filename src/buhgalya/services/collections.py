from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from buhgalya.models import (
    Collection,
    CollectionParticipant,
    CollectionPayment,
    CollectionRound,
    Person,
)
from buhgalya.services.debts import get_or_create_person


@dataclass(frozen=True)
class ParticipantView:
    id: UUID
    person_name: str
    target_rub: int | None
    paid_rub: int

    @property
    def balance_rub(self) -> int | None:
        return None if self.target_rub is None else self.target_rub - self.paid_rub

    @property
    def status(self) -> str:
        if self.target_rub is None:
            return "open"
        if self.paid_rub > self.target_rub:
            return "overpaid"
        if self.paid_rub == self.target_rub:
            return "paid"
        if self.paid_rub == 0:
            return "unpaid"
        return "partial"


async def create_collection(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    name: str,
    kind: str,
    default_target_rub: int | None,
    actor_id: int,
) -> Collection:
    collection = Collection(
        workspace_id=workspace_id,
        name=name,
        kind=kind,
        default_target_rub=default_target_rub,
        created_by_telegram_user_id=actor_id,
    )
    session.add(collection)
    await session.flush()
    period_key = datetime.now(UTC).strftime("%Y-%m") if kind == "monthly" else "one-time"
    session.add(CollectionRound(collection_id=collection.id, period_key=period_key, status="open"))
    await session.flush()
    return collection


async def current_round(session: AsyncSession, collection_id: UUID) -> CollectionRound:
    round_ = await session.scalar(
        select(CollectionRound)
        .where(CollectionRound.collection_id == collection_id, CollectionRound.status == "open")
        .order_by(CollectionRound.created_at.desc())
    )
    if round_ is None:
        raise LookupError("Открытый период сбора не найден")
    return round_


async def add_participant(
    session: AsyncSession,
    *,
    collection_id: UUID,
    person_name: str,
    target_rub: int | None,
) -> ParticipantView:
    collection = await session.get(Collection, collection_id)
    if collection is None:
        raise LookupError("Сбор не найден")
    round_ = await current_round(session, collection_id)
    person = await get_or_create_person(
        session, workspace_id=collection.workspace_id, name=person_name
    )
    participant = CollectionParticipant(
        round_id=round_.id,
        person_id=person.id,
        target_rub=target_rub if target_rub is not None else collection.default_target_rub,
    )
    session.add(participant)
    await session.flush()
    return ParticipantView(participant.id, person.name, participant.target_rub, 0)


async def add_payment(
    session: AsyncSession, *, participant_id: UUID, amount_rub: int, actor_id: int
) -> ParticipantView:
    participant = await session.get(CollectionParticipant, participant_id)
    if participant is None:
        raise LookupError("Участник сбора не найден")
    session.add(
        CollectionPayment(
            participant_id=participant.id,
            amount_rub=amount_rub,
            created_by_telegram_user_id=actor_id,
        )
    )
    await session.flush()
    return await get_participant(session, participant_id)


async def get_participant(session: AsyncSession, participant_id: UUID) -> ParticipantView:
    view = await session.execute(
        participant_status_query().where(CollectionParticipant.id == participant_id)
    )
    row = view.one_or_none()
    if row is None:
        raise LookupError("Участник сбора не найден")
    return participant_view(row.tuple())


def participant_status_query():
    paid = (
        select(
            CollectionPayment.participant_id,
            func.coalesce(func.sum(CollectionPayment.amount_rub), 0).label("paid"),
        )
        .where(CollectionPayment.deleted_at.is_(None))
        .group_by(CollectionPayment.participant_id)
        .subquery()
    )
    return (
        select(CollectionParticipant, Person, func.coalesce(paid.c.paid, 0))
        .join(Person, Person.id == CollectionParticipant.person_id)
        .outerjoin(paid, paid.c.participant_id == CollectionParticipant.id)
    )


def participant_view(row: tuple[CollectionParticipant, Person, int]) -> ParticipantView:
    participant, person, paid = row
    return ParticipantView(participant.id, person.name, participant.target_rub, int(paid))


async def collection_status(
    session: AsyncSession, collection_id: UUID
) -> tuple[Collection, CollectionRound, list[ParticipantView]]:
    collection = await session.get(Collection, collection_id)
    if collection is None:
        raise LookupError("Сбор не найден")
    round_ = await current_round(session, collection_id)
    rows = (
        await session.execute(
            participant_status_query().where(CollectionParticipant.round_id == round_.id)
        )
    ).all()
    return collection, round_, [participant_view(row.tuple()) for row in rows]
