from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from buhgalya.models import Debt, DebtRepayment, Person


@dataclass(frozen=True)
class DebtView:
    id: UUID
    person_id: UUID
    person_name: str
    amount_rub: int
    repaid_rub: int

    @property
    def balance_rub(self) -> int:
        return self.amount_rub - self.repaid_rub


async def get_or_create_person(session: AsyncSession, *, workspace_id: UUID, name: str) -> Person:
    person = await session.scalar(
        select(Person).where(Person.workspace_id == workspace_id, Person.name == name)
    )
    if person is None:
        person = Person(workspace_id=workspace_id, name=name)
        session.add(person)
        await session.flush()
    return person


async def create_debt(
    session: AsyncSession, *, workspace_id: UUID, person_name: str, amount_rub: int, actor_id: int
) -> DebtView:
    person = await get_or_create_person(session, workspace_id=workspace_id, name=person_name)
    debt = Debt(
        workspace_id=workspace_id,
        person_id=person.id,
        amount_rub=amount_rub,
        created_by_telegram_user_id=actor_id,
    )
    session.add(debt)
    await session.flush()
    return DebtView(debt.id, person.id, person.name, debt.amount_rub, 0)


async def add_repayment(
    session: AsyncSession, *, debt_id: UUID, amount_rub: int, actor_id: int
) -> DebtView:
    debt = await session.scalar(select(Debt).where(Debt.id == debt_id, Debt.deleted_at.is_(None)))
    if debt is None:
        raise LookupError("Долг не найден или удалён")
    repayment = DebtRepayment(
        debt_id=debt.id, amount_rub=amount_rub, created_by_telegram_user_id=actor_id
    )
    session.add(repayment)
    await session.flush()
    return await get_debt(session, debt_id)


async def update_debt_amount(session: AsyncSession, *, debt_id: UUID, amount_rub: int) -> DebtView:
    debt = await session.scalar(select(Debt).where(Debt.id == debt_id, Debt.deleted_at.is_(None)))
    if debt is None:
        raise LookupError("Долг не найден или удалён")
    debt.amount_rub = amount_rub
    await session.flush()
    return await get_debt(session, debt_id)


async def delete_debt(session: AsyncSession, *, debt_id: UUID, actor_id: int) -> None:
    debt = await session.scalar(select(Debt).where(Debt.id == debt_id, Debt.deleted_at.is_(None)))
    if debt is None:
        raise LookupError("Долг не найден или уже удалён")
    debt.deleted_at = datetime.now(UTC)
    debt.deleted_by_telegram_user_id = actor_id
    await session.flush()


def active_debts_query(workspace_id: UUID) -> Select[tuple[Debt, Person, int]]:
    repaid = (
        select(
            DebtRepayment.debt_id,
            func.coalesce(func.sum(DebtRepayment.amount_rub), 0).label("repaid"),
        )
        .where(DebtRepayment.deleted_at.is_(None))
        .group_by(DebtRepayment.debt_id)
        .subquery()
    )
    return (
        select(Debt, Person, func.coalesce(repaid.c.repaid, 0))
        .join(Person, Person.id == Debt.person_id)
        .outerjoin(repaid, repaid.c.debt_id == Debt.id)
        .where(Debt.workspace_id == workspace_id, Debt.deleted_at.is_(None))
        .order_by(Debt.created_at.desc())
    )


def debt_view(row: tuple[Debt, Person, int]) -> DebtView:
    debt, person, repaid = row
    return DebtView(debt.id, person.id, person.name, debt.amount_rub, int(repaid))


async def get_debt(session: AsyncSession, debt_id: UUID) -> DebtView:
    result = await session.execute(active_debts_query_for_id(debt_id))
    row = result.one_or_none()
    if row is None:
        raise LookupError("Долг не найден или удалён")
    return debt_view(row.tuple())


def active_debts_query_for_id(debt_id: UUID) -> Select[tuple[Debt, Person, int]]:
    repaid = (
        select(
            DebtRepayment.debt_id,
            func.coalesce(func.sum(DebtRepayment.amount_rub), 0).label("repaid"),
        )
        .where(DebtRepayment.deleted_at.is_(None))
        .group_by(DebtRepayment.debt_id)
        .subquery()
    )
    return (
        select(Debt, Person, func.coalesce(repaid.c.repaid, 0))
        .join(Person, Person.id == Debt.person_id)
        .outerjoin(repaid, repaid.c.debt_id == Debt.id)
        .where(Debt.id == debt_id, Debt.deleted_at.is_(None))
    )
